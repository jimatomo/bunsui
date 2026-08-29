"""Tests for yaml job declarations → SQLite sync (no execution)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from bunsui.config import load_config, write_config
from bunsui.db import connect
from bunsui.jobs import load_declared_jobs, parse_jobs, sync_jobs
from bunsui.project import init_project


def _clear_jobs_dir(root: Path) -> None:
    jobs = root / "jobs"
    if jobs.is_dir():
        shutil.rmtree(jobs)
    jobs.mkdir()


def _write_job_file(root: Path, filename: str, body: object) -> None:
    path = root / "jobs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_parse_jobs_rejects_bad_type() -> None:
    with pytest.raises(ValueError, match="type must be"):
        parse_jobs({"jobs": [{"name": "x", "type": "shell"}]})


def test_parse_jobs_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="unknown job"):
        parse_jobs(
            {
                "jobs": [
                    {
                        "name": "a",
                        "type": "python",
                        "depends_on": ["missing"],
                        "config": {"callable": "m:f"},
                    }
                ]
            }
        )


def test_sync_creates_updates_and_disables(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    paths = init_project(root, name="proj")
    _clear_jobs_dir(root)

    jobs_v1 = [
        {
            "name": "alpha",
            "type": "dbt",
            "execution_mode": "sync",
            "depends_on": [],
            "config": {"command": "run"},
        },
        {
            "name": "beta",
            "type": "python",
            "execution_mode": "async",
            "depends_on": ["alpha"],
            "config": {"callable": "pkg:fn"},
        },
    ]
    cfg = load_config(paths)
    cfg["jobs"] = jobs_v1
    write_config(paths.config_file, cfg)

    r1 = sync_jobs(paths)
    assert r1.created == 2
    assert r1.updated == 0
    assert r1.disabled == 0

    with connect(paths.sqlite_path) as conn:
        rows = {
            r["name"]: r
            for r in conn.execute(
                "SELECT name, job_type, execution_mode, enabled, config_json, depends_on_json "
                "FROM jobs ORDER BY name"
            ).fetchall()
        }
        assert set(rows) == {"alpha", "beta"}
        assert rows["alpha"]["job_type"] == "dbt"
        assert rows["beta"]["execution_mode"] == "async"
        assert json.loads(rows["beta"]["depends_on_json"]) == ["alpha"]
        assert json.loads(rows["alpha"]["config_json"]) == {"command": "run"}
        assert all(int(r["enabled"]) == 1 for r in rows.values())
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0

    r2 = sync_jobs(paths)
    assert r2.created == 0
    assert r2.updated == 0
    assert r2.disabled == 0

    jobs_v2 = [
        {
            "name": "beta",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": [],
            "config": {"callable": "pkg:other"},
        }
    ]
    cfg["jobs"] = jobs_v2
    write_config(paths.config_file, cfg)

    r3 = sync_jobs(paths)
    assert r3.created == 0
    assert r3.updated == 1
    assert r3.disabled == 1

    with connect(paths.sqlite_path) as conn:
        rows = {
            r["name"]: r
            for r in conn.execute(
                "SELECT name, job_type, execution_mode, enabled, config_json FROM jobs"
            ).fetchall()
        }
        assert int(rows["alpha"]["enabled"]) == 0
        assert int(rows["beta"]["enabled"]) == 1
        assert rows["beta"]["execution_mode"] == "sync"
        assert json.loads(rows["beta"]["config_json"]) == {"callable": "pkg:other"}

    cfg["jobs"] = jobs_v1
    write_config(paths.config_file, cfg)
    r4 = sync_jobs(paths)
    assert r4.created == 0
    assert r4.updated == 2
    assert r4.disabled == 0

    with connect(paths.sqlite_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        assert count == 2
        alpha = conn.execute(
            "SELECT enabled FROM jobs WHERE name = ?", ("alpha",)
        ).fetchone()
        assert int(alpha["enabled"]) == 1


def test_file_only_jobs_sync(tmp_path: Path) -> None:
    root = tmp_path / "files"
    root.mkdir()
    paths = init_project(root, name="files")
    _clear_jobs_dir(root)

    _write_job_file(
        root,
        "alpha.yaml",
        {
            "name": "alpha",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run"},
        },
    )
    _write_job_file(
        root,
        "group/beta.yml",
        {
            "jobs": [
                {
                    "name": "beta",
                    "type": "python",
                    "depends_on": ["alpha"],
                    "config": {"callable": "m:f"},
                }
            ]
        },
    )
    _write_job_file(
        root,
        "list.yaml",
        [
            {
                "name": "gamma",
                "type": "python",
                "depends_on": ["beta"],
                "config": {"callable": "m:g"},
            }
        ],
    )
    # Hidden / dot files ignored
    (root / "jobs" / ".skip.yaml").write_text(
        "name: hidden\ntype: python\nconfig: {callable: x:y}\n", encoding="utf-8"
    )

    decls = load_declared_jobs(paths)
    assert {d.name for d in decls} == {"alpha", "beta", "gamma"}
    assert {d.source for d in decls if d.name == "beta"} == {"jobs/group/beta.yml"}

    result = sync_jobs(paths)
    assert result.created == 3
    with connect(paths.sqlite_path) as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM jobs WHERE enabled = 1").fetchall()
        }
        assert names == {"alpha", "beta", "gamma"}


def test_inline_and_file_merge(tmp_path: Path) -> None:
    root = tmp_path / "merge"
    root.mkdir()
    paths = init_project(root, name="merge")
    _clear_jobs_dir(root)

    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "inline_job",
            "type": "python",
            "config": {"callable": "a:b"},
        }
    ]
    write_config(paths.config_file, cfg)
    _write_job_file(
        root,
        "file_job.yaml",
        {
            "name": "file_job",
            "type": "dbt",
            "depends_on": ["inline_job"],
            "config": {"command": "run"},
        },
    )

    decls = load_declared_jobs(paths)
    assert {d.name: d.source for d in decls} == {
        "inline_job": "bunsui.yaml",
        "file_job": "jobs/file_job.yaml",
    }
    result = sync_jobs(paths)
    assert result.created == 2


def test_duplicate_name_across_sources(tmp_path: Path) -> None:
    root = tmp_path / "dup"
    root.mkdir()
    paths = init_project(root, name="dup")
    _clear_jobs_dir(root)

    cfg = load_config(paths)
    cfg["jobs"] = [{"name": "same", "type": "dbt", "config": {"command": "run"}}]
    write_config(paths.config_file, cfg)
    _write_job_file(
        root,
        "same.yaml",
        {"name": "same", "type": "python", "config": {"callable": "x:y"}},
    )

    with pytest.raises(ValueError, match=r"duplicate job name 'same' in bunsui.yaml and jobs/same.yaml"):
        load_declared_jobs(paths)


def test_init_layout_writes_jobs_dir(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir()
    paths = init_project(root, name="demo")
    result = sync_jobs(paths)
    assert result.created >= 2

    cfg = load_config(paths)
    assert cfg.get("jobs") in (None, [])
    assert (paths.jobs_dir / "example_dbt.yaml").is_file()
    assert (paths.jobs_dir / "example_python.yaml").is_file()

    decls = load_declared_jobs(paths)
    assert {d.name for d in decls} == {"example_dbt", "example_python"}
    assert all(d.source.startswith("jobs/") for d in decls)
