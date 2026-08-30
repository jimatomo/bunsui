"""Tests for ``bunsui job run`` (python sync + async)."""

from __future__ import annotations

import shutil
import time
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


def test_run_python_async_succeeds_via_sqlite_poll(tmp_path: Path) -> None:
    root = tmp_path / "async_ok"
    root.mkdir()
    paths = init_project(root, name="async_ok")
    _clear_jobs_dir(root)
    (root / "slow.py").write_text(
        "import time\n"
        "def main():\n"
        "    time.sleep(0.2)\n"
        "    print('async ran')\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "slow.yaml",
        {
            "name": "slow_job",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "slow:main"},
        },
    )

    polled: list[str] = []
    result = run_job(
        paths,
        "slow_job",
        poll_interval=0.02,
        polled_statuses=polled,
    )
    assert result.status == "succeeded"
    assert "running" in polled
    assert polled[-1] == "succeeded"

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, finished_at FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "succeeded"
        assert row["finished_at"]


def test_run_python_async_records_failure(tmp_path: Path) -> None:
    root = tmp_path / "async_fail"
    root.mkdir()
    paths = init_project(root, name="async_fail")
    _clear_jobs_dir(root)
    (root / "async_boom.py").write_text(
        "def main():\n    raise ValueError('async boom')\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "async_boom.yaml",
        {
            "name": "async_boom",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "async_boom:main"},
        },
    )

    result = run_job(paths, "async_boom", poll_interval=0.02)
    assert result.status == "failed"
    assert result.error_message is not None
    assert "async boom" in result.error_message

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, error_message FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "failed"
        assert "async boom" in (row["error_message"] or "")


def test_run_python_async_no_wait_returns_running(tmp_path: Path) -> None:
    root = tmp_path / "async_nowait"
    root.mkdir()
    paths = init_project(root, name="async_nowait")
    _clear_jobs_dir(root)
    (root / "long.py").write_text(
        "import time\n"
        "def main():\n"
        "    time.sleep(2)\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "long.yaml",
        {
            "name": "long_job",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "long:main"},
        },
    )

    result = run_job(paths, "long_job", wait=False)
    assert result.status == "running"

    deadline = time.monotonic() + 3.0
    terminal = None
    while time.monotonic() < deadline:
        with connect(paths.sqlite_path) as conn:
            row = conn.execute(
                "SELECT status FROM job_runs WHERE id = ?",
                (result.run_id,),
            ).fetchone()
        terminal = row["status"]
        if terminal != "running":
            break
        time.sleep(0.05)
    assert terminal == "succeeded"


def test_run_python_async_dead_child_marks_failed(tmp_path: Path) -> None:
    root = tmp_path / "async_dead"
    root.mkdir()
    paths = init_project(root, name="async_dead")
    _clear_jobs_dir(root)
    (root / "exit_now.py").write_text(
        "import os\n"
        "def main():\n"
        "    os._exit(0)\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "dead.yaml",
        {
            "name": "dead_job",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "exit_now:main"},
        },
    )

    result = run_job(paths, "dead_job", poll_interval=0.02, timeout=1.0)
    assert result.status == "failed"
    assert result.error_message is not None
    assert "without writing terminal status" in result.error_message

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, error_message, finished_at FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "failed"
        assert row["finished_at"]


def test_run_python_async_timeout_marks_failed(tmp_path: Path) -> None:
    root = tmp_path / "async_timeout"
    root.mkdir()
    paths = init_project(root, name="async_timeout")
    _clear_jobs_dir(root)
    (root / "hang.py").write_text(
        "import time\n"
        "def main():\n"
        "    time.sleep(60)\n",
        encoding="utf-8",
    )
    _write_job_file(
        root,
        "hang.yaml",
        {
            "name": "hang_job",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "hang:main"},
        },
    )

    result = run_job(
        paths,
        "hang_job",
        poll_interval=0.02,
        timeout=0.15,
    )
    assert result.status == "failed"
    assert result.error_message is not None
    assert "timed out" in result.error_message

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "failed"


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


def test_init_sample_async_callable_runs(tmp_path: Path) -> None:
    root = tmp_path / "demo_async"
    root.mkdir()
    paths = init_project(root, name="demo_async")
    assert (paths.jobs_dir / "example_python_async.yaml").is_file()

    result = run_job(paths, "example_python_async", poll_interval=0.02)
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
