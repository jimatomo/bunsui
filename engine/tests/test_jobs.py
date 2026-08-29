"""Tests for yaml job declarations → SQLite sync (no execution)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from bunsui.config import load_config, write_config
from bunsui.db import connect
from bunsui.jobs import parse_jobs, sync_jobs
from bunsui.project import init_project


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
        # No runs written by sync
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0

    # Idempotent: same yaml → no churn
    r2 = sync_jobs(paths)
    assert r2.created == 0
    assert r2.updated == 0
    assert r2.disabled == 0

    # Update beta config + remove alpha from yaml → disable alpha, update beta
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

    # Re-add alpha → re-enable without creating a duplicate row
    cfg["jobs"] = jobs_v1
    write_config(paths.config_file, cfg)
    r4 = sync_jobs(paths)
    assert r4.created == 0
    assert r4.updated == 2  # alpha re-enabled + restored; beta restored to v1
    assert r4.disabled == 0

    with connect(paths.sqlite_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        assert count == 2
        alpha = conn.execute(
            "SELECT enabled FROM jobs WHERE name = ?", ("alpha",)
        ).fetchone()
        assert int(alpha["enabled"]) == 1


def test_init_then_job_sync_cli_smoke(tmp_path: Path) -> None:
    """Mirrors the documented success path without invoking Click."""
    root = tmp_path / "demo"
    root.mkdir()
    paths = init_project(root, name="demo")
    result = sync_jobs(paths)
    assert result.created >= 2

    text = paths.config_file.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert "jobs" in data
    assert any(j["type"] == "dbt" for j in data["jobs"])
    assert any(j["type"] == "python" for j in data["jobs"])
