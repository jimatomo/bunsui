"""Tests for ``bunsui job run`` (python sync/async + dbt sync)."""

from __future__ import annotations

import shutil
import stat
import time
from pathlib import Path

import pytest
import yaml

from bunsui.config import load_config, write_config
from bunsui.db import connect
from bunsui.project import init_project
from bunsui.runner import run_job


def _clear_jobs_dir(root: Path) -> None:
    jobs = root / "jobs"
    if jobs.is_dir():
        shutil.rmtree(jobs)
    jobs.mkdir()


def _write_job_file(root: Path, filename: str, body: object) -> None:
    path = root / "jobs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _write_dbt_stub(directory: Path, script: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "dbt"
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)

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


def test_run_dbt_succeeds_and_stores_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "dbt_ok"
    root.mkdir()
    paths = init_project(root, name="dbt_ok")
    _clear_jobs_dir(root)
    stub = _write_dbt_stub(
        tmp_path / "bin",
        '#!/bin/sh\necho "Running with dbt stub"\necho "Done."\nexit 0\n',
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_job",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run", "select": "example"},
        },
    )

    result = run_job(paths, "dbt_job")
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
        log = conn.execute(
            "SELECT log_kind, path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        assert log is not None
        assert log["log_kind"] == "combined"
        assert log["path"] == f"logs/{result.run_id}.log"
        content = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert "Running with dbt stub" in content


def test_run_dbt_failure_stores_error_and_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "dbt_fail"
    root.mkdir()
    paths = init_project(root, name="dbt_fail")
    _clear_jobs_dir(root)
    stub = _write_dbt_stub(
        tmp_path / "bin",
        "#!/bin/sh\n"
        'echo "Compilation Error in model bad"\n'
        "exit 1\n",
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_bad",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run", "select": "missing_model"},
        },
    )

    result = run_job(paths, "dbt_bad")
    assert result.status == "failed"
    assert result.error_message is not None
    assert "exited with code 1" in result.error_message
    # error_message stays short — not a full log dump
    assert "\n" not in result.error_message
    assert len(result.error_message) <= 220

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, error_message, finished_at FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "failed"
        assert row["finished_at"]
        assert "exited with code 1" in (row["error_message"] or "")
        log = conn.execute(
            "SELECT path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        assert log is not None
        content = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert "Compilation Error" in content


def test_build_dbt_argv_includes_select() -> None:
    from bunsui.runner import build_dbt_argv

    argv = build_dbt_argv(
        {"command": "run", "select": "example"},
        dbt_bin="/usr/bin/dbt",
    )
    assert argv == [
        "/usr/bin/dbt",
        "run",
        "--select",
        "example",
        "--project-dir",
        ".",
        "--profiles-dir",
        ".",
    ]


def test_parse_dbt_retry_policy_defaults() -> None:
    from bunsui.runner import (
        DEFAULT_DBT_RETRY_DELAY_SECONDS,
        parse_dbt_retry_policy,
    )

    policy = parse_dbt_retry_policy({"command": "run"})
    assert policy.retries == 0
    assert policy.retry_delay_seconds == DEFAULT_DBT_RETRY_DELAY_SECONDS
    assert policy.max_attempts == 1


def test_parse_dbt_retry_policy_rejects_invalid() -> None:
    from bunsui.runner import JobRunError, parse_dbt_retry_policy

    with pytest.raises(JobRunError, match="retries"):
        parse_dbt_retry_policy({"retries": -1})
    with pytest.raises(JobRunError, match="retries"):
        parse_dbt_retry_policy({"retries": 1.5})
    with pytest.raises(JobRunError, match="retries"):
        parse_dbt_retry_policy({"retries": True})
    with pytest.raises(JobRunError, match="retry_delay_seconds"):
        parse_dbt_retry_policy({"retry_delay_seconds": -0.1})
    with pytest.raises(JobRunError, match="retry_delay_seconds"):
        parse_dbt_retry_policy({"retry_delay_seconds": "slow"})


def test_run_dbt_retries_zero_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """retries=0 (default): one attempt, no attempt banners, fail immediately."""
    root = tmp_path / "dbt_r0"
    root.mkdir()
    paths = init_project(root, name="dbt_r0")
    _clear_jobs_dir(root)
    counter = tmp_path / "attempts_r0"
    stub = _write_dbt_stub(
        tmp_path / "bin_r0",
        "#!/bin/sh\n"
        f'echo x >> "{counter}"\n'
        'echo "fail once"\n'
        "exit 1\n",
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    sleeps: list[float] = []
    monkeypatch.setattr("bunsui.runner.time.sleep", sleeps.append)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_r0",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run", "retries": 0},
        },
    )

    result = run_job(paths, "dbt_r0")
    assert result.status == "failed"
    assert "after" not in (result.error_message or "")
    assert counter.read_text(encoding="utf-8").count("x") == 1
    assert sleeps == []

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 1
        log = conn.execute(
            "SELECT path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        content = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert "attempt" not in content
        assert "fail once" in content


def test_run_dbt_retries_succeeds_on_second_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First attempt runs configured command; second uses native ``dbt retry``."""
    root = tmp_path / "dbt_r2_ok"
    root.mkdir()
    paths = init_project(root, name="dbt_r2_ok")
    _clear_jobs_dir(root)
    counter = tmp_path / "attempts_r2_ok"
    argv_log = tmp_path / "argv_r2_ok"
    stub = _write_dbt_stub(
        tmp_path / "bin_r2_ok",
        "#!/bin/sh\n"
        f'echo x >> "{counter}"\n'
        f'echo "$*" >> "{argv_log}"\n'
        "mkdir -p target\n"
        'if [ "$1" = "retry" ]; then\n'
        '  echo "ok on dbt retry"\n'
        "  exit 0\n"
        "fi\n"
        'echo \'{"metadata":{},"results":[]}\' > target/run_results.json\n'
        'echo "transient fail"\n'
        "exit 1\n",
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    sleeps: list[float] = []
    monkeypatch.setattr("bunsui.runner.time.sleep", sleeps.append)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_retry_ok",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {
                "command": "run",
                "select": "example",
                "retries": 2,
                "retry_delay_seconds": 1.5,
            },
        },
    )

    result = run_job(paths, "dbt_retry_ok")
    assert result.status == "succeeded"
    assert result.error_message is None
    assert counter.read_text(encoding="utf-8").count("x") == 2
    assert sleeps == [1.5]
    argv_lines = argv_log.read_text(encoding="utf-8").strip().splitlines()
    assert argv_lines[0].startswith("run")
    assert argv_lines[1].startswith("retry")

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 1
        row = conn.execute(
            "SELECT status, error_message FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "succeeded"
        assert row["error_message"] is None
        log = conn.execute(
            "SELECT path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        content = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert "===== dbt attempt 1/3 =====" in content
        assert "===== dbt attempt 2/3 =====" in content
        assert "transient fail" in content
        assert "ok on dbt retry" in content
        assert "===== dbt attempt 3/3 =====" not in content


def test_run_dbt_retries_exhausted_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "dbt_r_ex"
    root.mkdir()
    paths = init_project(root, name="dbt_r_ex")
    _clear_jobs_dir(root)
    counter = tmp_path / "attempts_ex"
    argv_log = tmp_path / "argv_ex"
    stub = _write_dbt_stub(
        tmp_path / "bin_ex",
        "#!/bin/sh\n"
        f'echo x >> "{counter}"\n'
        f'echo "$*" >> "{argv_log}"\n'
        "mkdir -p target\n"
        'echo \'{"metadata":{},"results":[]}\' > target/run_results.json\n'
        'echo "always fail"\n'
        "exit 1\n",
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    sleeps: list[float] = []
    monkeypatch.setattr("bunsui.runner.time.sleep", sleeps.append)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_exhausted",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {
                "command": "run",
                "retries": 2,
                "retry_delay_seconds": 0.25,
            },
        },
    )

    result = run_job(paths, "dbt_exhausted")
    assert result.status == "failed"
    assert result.error_message is not None
    assert "exited with code 1" in result.error_message
    assert "after 3 attempts" in result.error_message
    assert counter.read_text(encoding="utf-8").count("x") == 3
    assert sleeps == [0.25, 0.25]
    argv_lines = argv_log.read_text(encoding="utf-8").strip().splitlines()
    assert argv_lines[0].startswith("run")
    assert all(line.startswith("retry") for line in argv_lines[1:])

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 1
        log = conn.execute(
            "SELECT path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        content = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert content.count("===== dbt attempt") == 3
        assert content.count("always fail") == 3


def test_run_dbt_retry_delay_honored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """retry_delay_seconds is passed to sleep before each native ``dbt retry``."""
    root = tmp_path / "dbt_delay"
    root.mkdir()
    paths = init_project(root, name="dbt_delay")
    _clear_jobs_dir(root)
    stub = _write_dbt_stub(
        tmp_path / "bin_delay",
        "#!/bin/sh\n"
        "mkdir -p target\n"
        'echo \'{"metadata":{},"results":[]}\' > target/run_results.json\n'
        "echo boom\n"
        "exit 1\n",
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    sleeps: list[float] = []
    monkeypatch.setattr("bunsui.runner.time.sleep", sleeps.append)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_delay",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {
                "command": "build",
                "retries": 1,
                "retry_delay_seconds": 3,
            },
        },
    )

    result = run_job(paths, "dbt_delay")
    assert result.status == "failed"
    assert sleeps == [3.0]


def test_run_dbt_retry_missing_run_results_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without target/run_results.json after failure, do not invent a dbt retry."""
    root = tmp_path / "dbt_no_rr"
    root.mkdir()
    paths = init_project(root, name="dbt_no_rr")
    _clear_jobs_dir(root)
    counter = tmp_path / "attempts_no_rr"
    stub = _write_dbt_stub(
        tmp_path / "bin_no_rr",
        "#!/bin/sh\n"
        f'echo x >> "{counter}"\n'
        'echo "fail without artifacts"\n'
        "exit 1\n",
    )
    monkeypatch.setenv("BUNSUI_DBT_BIN", stub)
    sleeps: list[float] = []
    monkeypatch.setattr("bunsui.runner.time.sleep", sleeps.append)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_no_rr",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {
                "command": "build",
                "retries": 2,
                "retry_delay_seconds": 1,
            },
        },
    )

    result = run_job(paths, "dbt_no_rr")
    assert result.status == "failed"
    assert result.error_message is not None
    assert "run_results.json is missing" in result.error_message
    assert "cannot invoke dbt retry" in result.error_message
    assert counter.read_text(encoding="utf-8").count("x") == 1
    assert sleeps == []

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 1


def test_build_dbt_retry_argv() -> None:
    from bunsui.runner import build_dbt_retry_argv

    assert build_dbt_retry_argv(dbt_bin="/usr/bin/dbt") == [
        "/usr/bin/dbt",
        "retry",
        "--project-dir",
        ".",
        "--profiles-dir",
        ".",
    ]


def test_run_dbt_invalid_retries_raises_before_run_row(
    tmp_path: Path,
) -> None:
    from bunsui.runner import JobRunError

    root = tmp_path / "dbt_bad_retry"
    root.mkdir()
    paths = init_project(root, name="dbt_bad_retry")
    _clear_jobs_dir(root)
    _write_job_file(
        root,
        "dbt.yaml",
        {
            "name": "dbt_bad_retry",
            "type": "dbt",
            "execution_mode": "sync",
            "config": {"command": "run", "retries": -5},
        },
    )

    with pytest.raises(JobRunError, match="retries"):
        run_job(paths, "dbt_bad_retry")

    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0


def test_run_dbt_real_duckdb_smoke(tmp_path: Path) -> None:
    """One offline smoke with real dbt-core + dbt-duckdb (skipped if dbt missing)."""
    if shutil.which("dbt") is None:
        pytest.skip("dbt CLI not on PATH")

    root = tmp_path / "demo"
    root.mkdir()
    paths = init_project(root, name="demo")

    result = run_job(paths, "example_dbt")
    assert result.status == "succeeded", result.error_message

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status FROM job_runs WHERE id = ?", (result.run_id,)
        ).fetchone()
        assert row["status"] == "succeeded"
        log = conn.execute(
            "SELECT path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        assert log is not None
        content = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert content.strip() != ""
        assets = list(
            conn.execute(
                "SELECT asset_key, asset_type, status FROM assets ORDER BY asset_key"
            )
        )
        assert len(assets) >= 1
        assert any(a["asset_type"] == "model" and "example" in a["asset_key"] for a in assets)
        assert all(
            a["status"] in {"materialized", "failed", "skipped"} for a in assets
        )


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
    """``run_job`` runs only the named job (chain walking is ``run_job_chain``)."""
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


def _run_names(paths: object) -> list[str]:
    with connect(paths.sqlite_path) as conn:  # type: ignore[attr-defined]
        return [
            r["name"]
            for r in conn.execute(
                "SELECT j.name FROM job_runs r JOIN jobs j ON j.id = r.job_id "
                "ORDER BY r.rowid"
            ).fetchall()
        ]


def test_chain_linear_success(tmp_path: Path) -> None:
    from bunsui.runner import resolve_dependency_order, run_job_chain

    root = tmp_path / "chain_ok"
    root.mkdir()
    paths = init_project(root, name="chain_ok")
    _clear_jobs_dir(root)
    marker = root / "order.txt"
    (root / "chain_ok_mod.py").write_text(
        "from pathlib import Path\n"
        f"MARKER = Path({str(marker)!r})\n"
        "def a():\n"
        "    MARKER.write_text(MARKER.read_text() + 'a' if MARKER.exists() else 'a')\n"
        "def b():\n"
        "    MARKER.write_text(MARKER.read_text() + 'b' if MARKER.exists() else 'b')\n",
        encoding="utf-8",
    )
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": [],
            "config": {"callable": "chain_ok_mod:a"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "chain_ok_mod:b"},
        },
    ]
    write_config(paths.config_file, cfg)

    assert resolve_dependency_order(paths, "job_b") == ["job_a", "job_b"]
    chain = run_job_chain(paths, "job_b", sync_first=False)
    assert chain.status == "succeeded"
    assert [r.job_name for r in chain.results] == ["job_a", "job_b"]
    assert _run_names(paths) == ["job_a", "job_b"]
    assert marker.read_text(encoding="utf-8") == "ab"


def test_chain_upstream_failure_stops(tmp_path: Path) -> None:
    from bunsui.runner import run_job_chain

    root = tmp_path / "chain_fail"
    root.mkdir()
    paths = init_project(root, name="chain_fail")
    _clear_jobs_dir(root)
    (root / "chain_fail_mod.py").write_text(
        "def boom():\n    raise RuntimeError('upstream boom')\n"
        "def leaf():\n    raise AssertionError('leaf must not run')\n",
        encoding="utf-8",
    )
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "sync",
            "config": {"callable": "chain_fail_mod:boom"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "chain_fail_mod:leaf"},
        },
    ]
    write_config(paths.config_file, cfg)

    chain = run_job_chain(paths, "job_b")
    assert chain.status == "failed"
    assert chain.failed_job == "job_a"
    assert len(chain.results) == 1
    assert _run_names(paths) == ["job_a"]


def test_chain_cycle_error(tmp_path: Path) -> None:
    from bunsui.runner import JobRunError, resolve_dependency_order

    root = tmp_path / "cycle"
    root.mkdir()
    paths = init_project(root, name="cycle")
    _clear_jobs_dir(root)
    (root / "cycle_mod.py").write_text("def main():\n    pass\n", encoding="utf-8")
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_b"],
            "config": {"callable": "cycle_mod:main"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "cycle_mod:main"},
        },
    ]
    write_config(paths.config_file, cfg)

    with pytest.raises(JobRunError, match="dependency cycle"):
        resolve_dependency_order(paths, "job_a")
    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0


def test_chain_missing_dep_error(tmp_path: Path) -> None:
    from bunsui.jobs import sync_jobs
    from bunsui.runner import JobRunError, resolve_dependency_order

    root = tmp_path / "missing"
    root.mkdir()
    paths = init_project(root, name="missing")
    _clear_jobs_dir(root)
    (root / "missing_mod.py").write_text("def main():\n    pass\n", encoding="utf-8")
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "upstream",
            "type": "python",
            "execution_mode": "sync",
            "config": {"callable": "missing_mod:main"},
        },
        {
            "name": "leaf",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["upstream"],
            "config": {"callable": "missing_mod:main"},
        },
    ]
    write_config(paths.config_file, cfg)
    sync_jobs(paths)

    with connect(paths.sqlite_path) as conn:
        conn.execute("UPDATE jobs SET enabled = 0 WHERE name = 'upstream'")
        conn.commit()

    with pytest.raises(JobRunError, match="missing or disabled job 'upstream'"):
        resolve_dependency_order(paths, "leaf", sync_first=False)
    with connect(paths.sqlite_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM job_runs").fetchone()["c"] == 0


def test_chain_no_deps_runs_one_job(tmp_path: Path) -> None:
    """CLI ``--no-deps`` path: ``run_job`` alone despite depends_on."""
    root = tmp_path / "no_deps"
    root.mkdir()
    paths = init_project(root, name="no_deps")
    _clear_jobs_dir(root)
    (root / "no_deps_mod.py").write_text(
        "def upstream():\n    raise RuntimeError('should not run')\n"
        "def leaf():\n    pass\n",
        encoding="utf-8",
    )
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "sync",
            "config": {"callable": "no_deps_mod:upstream"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "no_deps_mod:leaf"},
        },
    ]
    write_config(paths.config_file, cfg)

    result = run_job(paths, "job_b")
    assert result.status == "succeeded"
    assert _run_names(paths) == ["job_b"]


def test_chain_waits_for_async_upstream(tmp_path: Path) -> None:
    from bunsui.runner import run_job_chain

    root = tmp_path / "async_up"
    root.mkdir()
    paths = init_project(root, name="async_up")
    _clear_jobs_dir(root)
    (root / "async_up_mod.py").write_text(
        "import time\n"
        "def up():\n"
        "    time.sleep(0.15)\n"
        "def leaf():\n"
        "    pass\n",
        encoding="utf-8",
    )
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "async",
            "config": {"callable": "async_up_mod:up"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "async_up_mod:leaf"},
        },
    ]
    write_config(paths.config_file, cfg)

    chain = run_job_chain(paths, "job_b", poll_interval=0.02)
    assert chain.status == "succeeded"
    assert [r.job_name for r in chain.results] == ["job_a", "job_b"]
    assert all(r.status == "succeeded" for r in chain.results)
    assert _run_names(paths) == ["job_a", "job_b"]


def test_chain_diamond_runs_siblings_in_parallel(tmp_path: Path) -> None:
    """Diamond A→B, A→C, B+C→D: B and C start together before D."""
    from bunsui.runner import run_job_chain

    root = tmp_path / "diamond"
    root.mkdir()
    paths = init_project(root, name="diamond")
    _clear_jobs_dir(root)
    sqlite = str(paths.sqlite_path)

    (root / "diamond_mod.py").write_text(
        "import sqlite3\n"
        "import threading\n"
        "import time\n"
        "from pathlib import Path\n"
        "\n"
        f"SQLITE = {sqlite!r}\n"
        f"ROOT = Path({str(root)!r})\n"
        "b_started = threading.Event()\n"
        "c_started = threading.Event()\n"
        "\n"
        "def a():\n"
        "    pass\n"
        "\n"
        "def b():\n"
        "    b_started.set()\n"
        "    assert c_started.wait(timeout=2.0), 'C did not start alongside B'\n"
        "    time.sleep(0.05)\n"
        "\n"
        "def c():\n"
        "    c_started.set()\n"
        "    assert b_started.wait(timeout=2.0), 'B did not start alongside C'\n"
        "    time.sleep(0.05)\n"
        "\n"
        "def d():\n"
        "    conn = sqlite3.connect(SQLITE)\n"
        "    rows = list(\n"
        "        conn.execute(\n"
        "            'SELECT j.name, r.status FROM job_runs r '\n"
        "            'JOIN jobs j ON j.id = r.job_id'\n"
        "        )\n"
        "    )\n"
        "    conn.close()\n"
        "    by_name = {name: status for name, status in rows}\n"
        "    assert by_name.get('job_b') == 'succeeded'\n"
        "    assert by_name.get('job_c') == 'succeeded'\n"
        "    # D's own running row may already exist before the callable body.\n"
        "    assert by_name.get('job_d') in (None, 'running')\n"
        "    (ROOT / 'd_gate.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": [],
            "config": {"callable": "diamond_mod:a"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "diamond_mod:b"},
        },
        {
            "name": "job_c",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "diamond_mod:c"},
        },
        {
            "name": "job_d",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_b", "job_c"],
            "config": {"callable": "diamond_mod:d"},
        },
    ]
    write_config(paths.config_file, cfg)

    waves: list[list[str]] = []

    def on_wave(_n: int, jobs: object) -> None:
        waves.append([str(j) for j in jobs])  # type: ignore[union-attr]

    chain = run_job_chain(paths, "job_d", on_wave=on_wave)
    assert chain.status == "succeeded"
    assert chain.order == ("job_a", "job_b", "job_c", "job_d")
    assert [r.job_name for r in chain.results] == [
        "job_a",
        "job_b",
        "job_c",
        "job_d",
    ]
    assert ["job_b", "job_c"] in waves
    names = _run_names(paths)
    assert names[0] == "job_a"
    assert set(names[1:3]) == {"job_b", "job_c"}
    assert names[3] == "job_d"
    assert (root / "d_gate.txt").read_text(encoding="utf-8") == "ok"


def test_chain_sibling_failure_skips_downstream(tmp_path: Path) -> None:
    """If one sibling fails, wait for the other but do not start D."""
    from bunsui.runner import run_job_chain

    root = tmp_path / "sib_fail"
    root.mkdir()
    paths = init_project(root, name="sib_fail")
    _clear_jobs_dir(root)
    (root / "sib_fail_mod.py").write_text(
        "import threading\n"
        "import time\n"
        "b_started = threading.Event()\n"
        "c_started = threading.Event()\n"
        "\n"
        "def a():\n"
        "    pass\n"
        "\n"
        "def b():\n"
        "    b_started.set()\n"
        "    assert c_started.wait(timeout=2.0)\n"
        "    raise RuntimeError('sibling boom')\n"
        "\n"
        "def c():\n"
        "    c_started.set()\n"
        "    assert b_started.wait(timeout=2.0)\n"
        "    time.sleep(0.1)  # still in-flight when B fails\n"
        "\n"
        "def d():\n"
        "    raise AssertionError('D must not run')\n",
        encoding="utf-8",
    )
    cfg = load_config(paths)
    cfg["jobs"] = [
        {
            "name": "job_a",
            "type": "python",
            "execution_mode": "sync",
            "config": {"callable": "sib_fail_mod:a"},
        },
        {
            "name": "job_b",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "sib_fail_mod:b"},
        },
        {
            "name": "job_c",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_a"],
            "config": {"callable": "sib_fail_mod:c"},
        },
        {
            "name": "job_d",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["job_b", "job_c"],
            "config": {"callable": "sib_fail_mod:d"},
        },
    ]
    write_config(paths.config_file, cfg)

    chain = run_job_chain(paths, "job_d")
    assert chain.status == "failed"
    assert chain.failed_job == "job_b"
    result_names = {r.job_name for r in chain.results}
    assert result_names == {"job_a", "job_b", "job_c"}
    assert "job_d" not in result_names
    assert set(_run_names(paths)) == {"job_a", "job_b", "job_c"}
    c_result = next(r for r in chain.results if r.job_name == "job_c")
    assert c_result.status == "succeeded"