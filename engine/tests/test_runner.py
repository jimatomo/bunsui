"""Tests for ``bunsui job run`` (python + sync only)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from bunsui.config import load_config, write_config
from bunsui.db import connect
from bunsui.jobs import sync_jobs
from bunsui.project import init_project
from bunsui.runner import JobRunError, run_job


def _clear_jobs_dir(root: Path) -> None:
    jobs = root / "jobs"
    if jobs.is_dir():
        shutil.rmtree(jobs)
    jobs.mkdir()


def _write_job_file(root: Path, filename: str, body: object) -> None:
    path = root / "jobs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_run_python_sync_succeeds(tmp_path: Path) -> None:
    root = tmp_path / "ok"
    root.mkdir()
    paths = init_project(root, name="ok")
    _clear_jobs_dir(root)
    (root / "ok_mod.py").write_text(
        "def main():\n    print('ran')\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "ok.yaml",
        {
            "name": "ok_job",
            "type": "python",
            "execution_mode": "sync",
            "config": {"callable": "ok_mod:main"},
        },
    )

    result = run_job(paths, "ok_job")
    assert result.status == "succeeded"
    assert result.error_message is None

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, started_at, finished_at, error_message FROM job_runs "
            "WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "succeeded"
        assert row["started_at"]
        assert row["finished_at"]
        assert row["error_message"] is None
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 1


def test_run_python_sync_records_failure(tmp_path: Path) -> None:
    root = tmp_path / "fail"
    root.mkdir()
    paths = init_project(root, name="fail")
    _clear_jobs_dir(root)
    (root / "boom.py").write_text(
        "def main():\n    raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "boom.yaml",
        {
            "name": "boom_job",
            "type": "python",
            "execution_mode": "sync",
            "config": {"callable": "boom:main"},
        },
    )

    result = run_job(paths, "boom_job")
    assert result.status == "failed"
    assert result.error_message is not None
    assert "boom" in result.error_message

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, error_message, finished_at FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "failed"
        assert "boom" in (row["error_message"] or "")
        assert row["finished_at"]


def test_run_rejects_dbt_without_run_row(tmp_path: Path) -> None:
    root = tmp_path / "dbt"
    root.mkdir()
    paths = init_project(root, name="dbt")
    _clear_jobs_dir(root)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_job",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run"},
        },
    )
    sync_jobs(paths)

    with pytest.raises(JobRunError, match="only type=python"):
        run_job(paths, "dbt_job", sync_first=False)

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0


def test_run_rejects_async_without_run_row(tmp_path: Path) -> None:
    root = tmp_path / "async"
    root.mkdir()
    paths = init_project(root, name="async")
    _clear_jobs_dir(root)
    (root / "async_mod.py").write_text("def main():\n    pass\n", encoding="utf-8")
    _write_job_file(
        root,
        "async.yaml",
        {
            "name": "async_job",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "async_mod:main"},
        },
    )
    sync_jobs(paths)

    with pytest.raises(JobRunError, match="only execution_mode=sync"):
        run_job(paths, "async_job", sync_first=False)

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0


def test_init_sample_callable_runs(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir()
    paths = init_project(root, name="demo")
    assert (root / "sample.py").is_file()

    result = run_job(paths, "example_python")
    assert result.status == "succeeded"

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status FROM job_runs WHERE id = ?", (result.run_id,)
        ).fetchone()
        assert row["status"] == "succeeded"


def test_run_does_not_walk_depends_on(tmp_path: Path) -> None:
    """Named job runs alone even when depends_on lists another job."""
    root = tmp_path / "deps"
    root.mkdir()
    paths = init_project(root, name="deps")
    _clear_jobs_dir(root)
    (root / "leaf.py").write_text("def main():\n    pass\n", encoding="utf-8")
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "upstream",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run"},
        },
        {
            "name": "leaf",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["upstream"],
            "config": {"callable": "leaf:main"},
        },
    ]
    write_config(paths.config_file, cfg)

    result = run_job(paths, "leaf")
    assert result.status == "succeeded"
    with connect(paths.sqlite_path) as conn:
        # Only the named job produced a run (upstream dbt was not executed).
        names = [
            r["name"]
            for r in conn.execute(
                "SELECT j.name FROM job_runs r JOIN jobs j ON j.id = r.job_id"
            ).fetchall()
        ]
        assert names == ["leaf"]
