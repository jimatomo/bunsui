"""Run a single job and record ``job_runs``.

Supports ``type=python`` (``execution_mode=sync`` in-process or ``async`` child +
SQLite poll) and ``type=dbt`` (``execution_mode=sync`` subprocess). Does not walk
``depends_on`` or ingest assets / ``run_results.json``.
"""

from __future__ import annotations

import importlib
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.jobs import sync_jobs
from bunsui.paths import LOGS_DIRNAME, ProjectPaths

TERMINAL_STATUSES = frozenset({"succeeded", "failed"})
DEFAULT_POLL_INTERVAL_S = 0.05
DEFAULT_ASYNC_TIMEOUT_S = 300.0
# Keep error_message short; full stdout/stderr lives in the logs file + row.
_ERROR_MESSAGE_MAX = 200


@dataclass(frozen=True)
class RunResult:
    """Outcome of one ``job run`` invocation."""

    run_id: str
    job_name: str
    status: str  # running | succeeded | failed
    error_message: str | None = None


class JobRunError(Exception):
    """User-facing error before or instead of a successful run (no hanging row)."""


def _parse_callable(spec: str) -> tuple[str, str]:
    if not isinstance(spec, str) or ":" not in spec:
        raise JobRunError(
            f"config.callable must be 'module:function', got {spec!r}"
        )
    module_name, _, func_name = spec.partition(":")
    module_name = module_name.strip()
    func_name = func_name.strip()
    if not module_name or not func_name:
        raise JobRunError(
            f"config.callable must be 'module:function', got {spec!r}"
        )
    return module_name, func_name


def _load_callable(project_root: str, callable_spec: str) -> Any:
    module_name, func_name = _parse_callable(callable_spec)
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 — surface import errors to the operator
        raise JobRunError(f"failed to import {module_name!r}: {exc}") from exc
    try:
        fn = getattr(module, func_name)
    except AttributeError as exc:
        raise JobRunError(
            f"module {module_name!r} has no attribute {func_name!r}"
        ) from exc
    if not callable(fn):
        raise JobRunError(f"{callable_spec!r} is not callable")
    return fn


def _finish_run(
    conn: Any,
    *,
    run_id: str,
    status: str,
    error_message: str | None,
    finished_at: str,
) -> None:
    conn.execute(
        """
        UPDATE job_runs SET
            status = ?,
            finished_at = ?,
            error_message = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (status, finished_at, error_message, finished_at, run_id),
    )
    conn.commit()


def _read_run_status(
    sqlite_path: str | Path,
    run_id: str,
) -> tuple[str, str | None]:
    with connect(sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, error_message FROM job_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        raise JobRunError(f"job run {run_id!r} not found in SQLite")
    return str(row["status"]), row["error_message"]


def _insert_running_run(
    conn: Any,
    *,
    run_id: str,
    job_id: str,
    trigger: str,
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO job_runs (
            id, job_id, status, trigger, started_at, finished_at,
            error_message, created_at, updated_at
        ) VALUES (?, ?, 'running', ?, ?, NULL, NULL, ?, ?)
        """,
        (run_id, job_id, trigger, now, now, now),
    )
    conn.commit()


def _async_worker(
    sqlite_path: str,
    run_id: str,
    project_root: str,
    callable_spec: str,
) -> None:
    """Child entrypoint: run callable and write terminal status to SQLite."""
    try:
        fn = _load_callable(project_root, callable_spec)
        fn()
    except Exception as exc:  # noqa: BLE001 — record any callable failure
        finished = utc_now_iso()
        message = f"{type(exc).__name__}: {exc}"
        with connect(sqlite_path) as conn:
            _finish_run(
                conn,
                run_id=run_id,
                status="failed",
                error_message=message,
                finished_at=finished,
            )
        return

    finished = utc_now_iso()
    with connect(sqlite_path) as conn:
        _finish_run(
            conn,
            run_id=run_id,
            status="succeeded",
            error_message=None,
            finished_at=finished,
        )


def _fail_stale_run(
    sqlite_path: str | Path,
    run_id: str,
    *,
    message: str,
    proc: mp.Process | None = None,
) -> RunResult:
    finished = utc_now_iso()
    with connect(sqlite_path) as conn:
        row = conn.execute(
            "SELECT status FROM job_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is not None and row["status"] == "running":
            _finish_run(
                conn,
                run_id=run_id,
                status="failed",
                error_message=message,
                finished_at=finished,
            )
    if proc is not None and proc.is_alive():
        proc.terminate()
        proc.join(timeout=1.0)
    return RunResult(
        run_id=run_id,
        job_name="",
        status="failed",
        error_message=message,
    )


def _poll_until_terminal(
    sqlite_path: str | Path,
    run_id: str,
    *,
    proc: mp.Process,
    poll_interval: float,
    timeout: float,
    polled_statuses: list[str] | None = None,
) -> tuple[str, str | None]:
    """Poll SQLite until status leaves ``running`` or timeout / dead child."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, error_message = _read_run_status(sqlite_path, run_id)
        if polled_statuses is not None:
            polled_statuses.append(status)
        if status in TERMINAL_STATUSES:
            return status, error_message
        if not proc.is_alive():
            _fail_stale_run(
                sqlite_path,
                run_id,
                message="child process exited without writing terminal status",
                proc=proc,
            )
            return "failed", "child process exited without writing terminal status"
        time.sleep(poll_interval)

    _fail_stale_run(
        sqlite_path,
        run_id,
        message=f"timed out after {timeout:g}s waiting for job completion",
        proc=proc,
    )
    return "failed", f"timed out after {timeout:g}s waiting for job completion"


def _run_sync_python(
    conn: Any,
    *,
    run_id: str,
    fn: Any,
    job_name: str,
) -> RunResult:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — record any callable failure
        finished = utc_now_iso()
        message = f"{type(exc).__name__}: {exc}"
        _finish_run(
            conn,
            run_id=run_id,
            status="failed",
            error_message=message,
            finished_at=finished,
        )
        return RunResult(
            run_id=run_id,
            job_name=job_name,
            status="failed",
            error_message=message,
        )

    finished = utc_now_iso()
    _finish_run(
        conn,
        run_id=run_id,
        status="succeeded",
        error_message=None,
        finished_at=finished,
    )
    return RunResult(run_id=run_id, job_name=job_name, status="succeeded")


def _run_async_python(
    paths: ProjectPaths,
    *,
    run_id: str,
    job_id: str,
    job_name: str,
    callable_spec: str,
    trigger: str,
    wait: bool,
    poll_interval: float,
    timeout: float,
    polled_statuses: list[str] | None = None,
) -> RunResult:
    now = utc_now_iso()
    sqlite_path = str(paths.sqlite_path)
    with connect(paths.sqlite_path) as conn:
        _insert_running_run(
            conn,
            run_id=run_id,
            job_id=job_id,
            trigger=trigger,
            now=now,
        )

    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=_async_worker,
        args=(sqlite_path, run_id, str(paths.root), str(callable_spec)),
        # Not a daemon: --no-wait returns while the parent exits; daemons are
        # killed on parent exit and would never write terminal status to SQLite.
        daemon=False,
    )
    proc.start()

    if not wait:
        return RunResult(run_id=run_id, job_name=job_name, status="running")

    status, error_message = _poll_until_terminal(
        paths.sqlite_path,
        run_id,
        proc=proc,
        poll_interval=poll_interval,
        timeout=timeout,
        polled_statuses=polled_statuses,
    )
    return RunResult(
        run_id=run_id,
        job_name=job_name,
        status=status,
        error_message=error_message,
    )


def _dbt_executable() -> str:
    """Resolve the dbt CLI binary (override with ``BUNSUI_DBT_BIN`` for tests)."""
    override = os.environ.get("BUNSUI_DBT_BIN")
    if override:
        return override
    found = shutil.which("dbt")
    if found:
        return found
    return "dbt"


def build_dbt_argv(config: dict[str, Any], *, dbt_bin: str | None = None) -> list[str]:
    """Build ``dbt <command> [--select …] --project-dir . --profiles-dir .``."""
    command = config.get("command")
    if not isinstance(command, str) or not command.strip():
        raise JobRunError("dbt job config.command is required (e.g. run, build, test)")
    command = command.strip()
    if any(ch.isspace() for ch in command):
        raise JobRunError(
            f"dbt job config.command must be a single subcommand, got {command!r}"
        )

    argv = [dbt_bin or _dbt_executable(), command]
    select = config.get("select")
    if select is not None and select != "":
        if not isinstance(select, str):
            raise JobRunError("dbt job config.select must be a string when set")
        argv.extend(["--select", select.strip()])
    argv.extend(["--project-dir", ".", "--profiles-dir", "."])
    return argv


def _short_dbt_error(returncode: int, output: str) -> str:
    last = ""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            last = stripped
            break
    base = f"dbt exited with code {returncode}"
    if not last:
        return base
    if len(last) > _ERROR_MESSAGE_MAX:
        last = last[: _ERROR_MESSAGE_MAX - 3] + "..."
    return f"{base}: {last}"


def _store_run_log(
    conn: Any,
    *,
    paths: ProjectPaths,
    run_id: str,
    output: str,
    created_at: str,
) -> str:
    """Write combined stdout/stderr under ``logs/`` and insert a ``logs`` row.

    Returns the relative path stored in SQLite (under the project root).
    """
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    rel = f"{LOGS_DIRNAME}/{run_id}.log"
    abs_path = paths.root / rel
    abs_path.write_text(output, encoding="utf-8")
    conn.execute(
        """
        INSERT INTO logs (id, job_run_id, log_kind, path, blob_pointer, created_at)
        VALUES (?, ?, 'combined', ?, NULL, ?)
        """,
        (str(uuid.uuid4()), run_id, rel, created_at),
    )
    conn.commit()
    return rel


def _run_sync_dbt(
    paths: ProjectPaths,
    *,
    run_id: str,
    job_id: str,
    job_name: str,
    config: dict[str, Any],
    trigger: str,
) -> RunResult:
    if not paths.dbt_dir.is_dir():
        raise JobRunError(f"dbt directory not found: {paths.dbt_dir}")
    project_yml = paths.dbt_dir / "dbt_project.yml"
    if not project_yml.is_file():
        raise JobRunError(f"missing dbt_project.yml in {paths.dbt_dir}")

    argv = build_dbt_argv(config)
    now = utc_now_iso()
    with connect(paths.sqlite_path) as conn:
        _insert_running_run(
            conn,
            run_id=run_id,
            job_id=job_id,
            trigger=trigger,
            now=now,
        )

    try:
        completed = subprocess.run(
            argv,
            cwd=str(paths.dbt_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        finished = utc_now_iso()
        message = f"dbt executable not found: {argv[0]}"
        with connect(paths.sqlite_path) as conn:
            _store_run_log(
                conn,
                paths=paths,
                run_id=run_id,
                output=f"{message}\n{exc}\n",
                created_at=finished,
            )
            _finish_run(
                conn,
                run_id=run_id,
                status="failed",
                error_message=message,
                finished_at=finished,
            )
        return RunResult(
            run_id=run_id,
            job_name=job_name,
            status="failed",
            error_message=message,
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if stdout and stderr:
        combined = stdout
        if not combined.endswith("\n"):
            combined += "\n"
        combined += stderr
    else:
        combined = stdout or stderr

    finished = utc_now_iso()
    if completed.returncode == 0:
        status = "succeeded"
        error_message = None
    else:
        status = "failed"
        error_message = _short_dbt_error(completed.returncode, combined)

    with connect(paths.sqlite_path) as conn:
        _store_run_log(
            conn,
            paths=paths,
            run_id=run_id,
            output=combined,
            created_at=finished,
        )
        _finish_run(
            conn,
            run_id=run_id,
            status=status,
            error_message=error_message,
            finished_at=finished,
        )

    return RunResult(
        run_id=run_id,
        job_name=job_name,
        status=status,
        error_message=error_message,
    )


def run_job(
    paths: ProjectPaths,
    job_name: str,
    *,
    sync_first: bool = True,
    trigger: str = "manual",
    wait: bool = True,
    poll_interval: float = DEFAULT_POLL_INTERVAL_S,
    timeout: float = DEFAULT_ASYNC_TIMEOUT_S,
    polled_statuses: list[str] | None = None,
) -> RunResult:
    """Sync declarations (optional), run one job, write ``job_runs``.

    Python sync jobs run in-process. Python async jobs spawn a child that writes
    terminal status into SQLite; the parent waits by polling ``job_runs.status``.
    dbt jobs run ``dbt`` as a sync subprocess and store combined stdout/stderr
    in the ``logs`` table (filesystem path under ``logs/``).

    Validation failures (missing / disabled / bad config) raise ``JobRunError``
    without leaving a run row.
    """
    if sync_first:
        sync_jobs(paths)
    else:
        bootstrap_sqlite(paths.sqlite_path)

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT id, name, job_type, config_json, execution_mode, enabled "
            "FROM jobs WHERE name = ?",
            (job_name,),
        ).fetchone()
        if row is None:
            raise JobRunError(
                f"job {job_name!r} not found in SQLite "
                "(run `bunsui job sync` or check the name)"
            )
        if int(row["enabled"]) != 1:
            raise JobRunError(f"job {job_name!r} is disabled")

        try:
            config = json.loads(row["config_json"] or "{}")
        except json.JSONDecodeError as exc:
            raise JobRunError(
                f"job {job_name!r} has invalid config_json: {exc}"
            ) from exc
        if not isinstance(config, dict):
            raise JobRunError(f"job {job_name!r} config must be a JSON object")

        job_type = row["job_type"]
        execution_mode = row["execution_mode"]
        run_id = str(uuid.uuid4())
        job_id = row["id"]

        if job_type == "dbt":
            if execution_mode != "sync":
                raise JobRunError(
                    f"job {job_name!r} has execution_mode={execution_mode!r}; "
                    "dbt jobs only support sync for now"
                )
            # Validate argv before inserting a run row.
            build_dbt_argv(config)
            # Release connection; dbt path opens its own for insert/update.
        elif job_type == "python":
            callable_spec = config.get("callable")
            if not callable_spec:
                raise JobRunError(f"job {job_name!r} config.callable is required")
            fn = _load_callable(str(paths.root), str(callable_spec))

            if execution_mode == "async":
                pass  # fall through to async helper after with-block
            elif execution_mode == "sync":
                now = utc_now_iso()
                _insert_running_run(
                    conn,
                    run_id=run_id,
                    job_id=job_id,
                    trigger=trigger,
                    now=now,
                )
                return _run_sync_python(
                    conn,
                    run_id=run_id,
                    fn=fn,
                    job_name=job_name,
                )
            else:
                raise JobRunError(
                    f"job {job_name!r} has execution_mode={execution_mode!r}; "
                    "expected sync or async"
                )
        else:
            raise JobRunError(
                f"job {job_name!r} has type={job_type!r}; "
                "supported types are python and dbt"
            )

    if job_type == "dbt":
        return _run_sync_dbt(
            paths,
            run_id=run_id,
            job_id=job_id,
            job_name=job_name,
            config=config,
            trigger=trigger,
        )

    return _run_async_python(
        paths,
        run_id=run_id,
        job_id=job_id,
        job_name=job_name,
        callable_spec=str(callable_spec),
        trigger=trigger,
        wait=wait,
        poll_interval=poll_interval,
        timeout=timeout,
        polled_statuses=polled_statuses,
    )
