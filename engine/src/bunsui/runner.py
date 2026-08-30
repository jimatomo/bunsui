"""Run a single Python job and record ``job_runs``.

Supports ``type=python`` with ``execution_mode=sync`` (in-process) or ``async``
(child process + SQLite status polling). Does not walk ``depends_on``, run dbt,
or ingest assets.
"""

from __future__ import annotations

import importlib
import json
import multiprocessing as mp
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.jobs import sync_jobs
from bunsui.paths import ProjectPaths

TERMINAL_STATUSES = frozenset({"succeeded", "failed"})
DEFAULT_POLL_INTERVAL_S = 0.05
DEFAULT_ASYNC_TIMEOUT_S = 300.0


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
        daemon=True,
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
    """Sync declarations (optional), run one python job, write ``job_runs``.

    Sync jobs run in-process. Async jobs spawn a child that writes terminal status
    into SQLite; the parent waits by polling ``job_runs.status`` (not ``proc.wait()``).

    Validation failures (missing / disabled / dbt / bad callable) raise
    ``JobRunError`` without leaving a run row.
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
        if row["job_type"] != "python":
            raise JobRunError(
                f"job {job_name!r} has type={row['job_type']!r}; "
                "only type=python is supported by `bunsui job run` for now"
            )

        try:
            config = json.loads(row["config_json"] or "{}")
        except json.JSONDecodeError as exc:
            raise JobRunError(
                f"job {job_name!r} has invalid config_json: {exc}"
            ) from exc
        if not isinstance(config, dict):
            raise JobRunError(f"job {job_name!r} config must be a JSON object")
        callable_spec = config.get("callable")
        if not callable_spec:
            raise JobRunError(f"job {job_name!r} config.callable is required")

        fn = _load_callable(str(paths.root), str(callable_spec))

        run_id = str(uuid.uuid4())
        execution_mode = row["execution_mode"]

        if execution_mode == "async":
            # Release connection before spawning; async path opens its own.
            job_id = row["id"]
        elif execution_mode == "sync":
            now = utc_now_iso()
            _insert_running_run(
                conn,
                run_id=run_id,
                job_id=row["id"],
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
