"""Run a single sync Python job and record ``job_runs``.

Only ``type=python`` + ``execution_mode=sync`` is supported here. Does not walk
``depends_on``, run dbt, or poll async jobs.
"""

from __future__ import annotations

import importlib
import json
import sys
import uuid
from dataclasses import dataclass
from typing import Any

from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.jobs import sync_jobs
from bunsui.paths import ProjectPaths


@dataclass(frozen=True)
class RunResult:
    """Outcome of one ``job run`` invocation."""

    run_id: str
    job_name: str
    status: str  # succeeded | failed
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


def run_job(
    paths: ProjectPaths,
    job_name: str,
    *,
    sync_first: bool = True,
    trigger: str = "manual",
) -> RunResult:
    """Sync declarations (optional), run one python+sync job, write ``job_runs``.

    Validation failures (missing / disabled / dbt / async / bad callable) raise
    ``JobRunError`` without leaving a run row. Callable exceptions produce a
    ``failed`` row and return ``RunResult(status='failed')``.
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
        if row["execution_mode"] != "sync":
            raise JobRunError(
                f"job {job_name!r} has execution_mode={row['execution_mode']!r}; "
                "only execution_mode=sync is supported for now"
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

        # Resolve callable before inserting a run row so bad specs leave no row.
        fn = _load_callable(str(paths.root), str(callable_spec))

        run_id = str(uuid.uuid4())
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO job_runs (
                id, job_id, status, trigger, started_at, finished_at,
                error_message, created_at, updated_at
            ) VALUES (?, ?, 'running', ?, ?, NULL, NULL, ?, ?)
            """,
            (run_id, row["id"], trigger, now, now, now),
        )
        conn.commit()

        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — record any callable failure
            finished = utc_now_iso()
            message = f"{type(exc).__name__}: {exc}"
            # Keep traceback out of SQLite; operators can see it on stderr via CLI.
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
