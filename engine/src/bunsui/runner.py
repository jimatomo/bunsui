"""Run jobs and record ``job_runs``.

Supports ``type=python`` (``execution_mode=sync`` in-process or ``async`` child +
SQLite poll) and ``type=dbt`` (``execution_mode=sync`` subprocess + ``run_results``
asset ingest, with optional ``config.retries``). ``run_job`` runs one named job;
``run_job_chain`` walks ``depends_on`` in topological waves (independent siblings
in parallel) and stops starting new waves after a failure.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bunsui.config import load_config
from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.jobs import sync_jobs
from bunsui.paths import LOGS_DIRNAME, ProjectPaths
from bunsui.run_results import ingest_dbt_run_results

TERMINAL_STATUSES = frozenset({"succeeded", "failed"})
DEFAULT_POLL_INTERVAL_S = 0.05
DEFAULT_ASYNC_TIMEOUT_S = 300.0
# dbt-only retry defaults (python jobs ignore these config keys).
DEFAULT_DBT_RETRIES = 0
DEFAULT_DBT_RETRY_DELAY_SECONDS = 2.0
# Keep error_message short; full stdout/stderr lives in the logs file + row.
_ERROR_MESSAGE_MAX = 200


@dataclass(frozen=True)
class RunResult:
    """Outcome of one ``job run`` invocation."""

    run_id: str
    job_name: str
    status: str  # running | succeeded | failed
    error_message: str | None = None


@dataclass(frozen=True)
class ChainResult:
    """Outcome of a ``depends_on`` chain (topo order + per-step results).

    ``results`` are appended wave-by-wave; within a wave, by job name (stable).
    Fail-fast: after any failure, in-flight siblings in that wave still finish
    writing ``job_runs``, but no further waves start.
    """

    order: tuple[str, ...]
    results: tuple[RunResult, ...]

    @property
    def job_name(self) -> str:
        return self.order[-1] if self.order else ""

    @property
    def status(self) -> str:
        if any(r.status == "failed" for r in self.results):
            return "failed"
        if any(r.status == "running" for r in self.results):
            return "running"
        return "succeeded"

    @property
    def run_id(self) -> str | None:
        for result in self.results:
            if result.status == "failed":
                return result.run_id
        return self.results[-1].run_id if self.results else None

    @property
    def error_message(self) -> str | None:
        for result in self.results:
            if result.status == "failed":
                return result.error_message
        return self.results[-1].error_message if self.results else None

    @property
    def failed_job(self) -> str | None:
        for result in self.results:
            if result.status == "failed":
                return result.job_name
        return None


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


@dataclass(frozen=True)
class DbtRetryPolicy:
    """How many times to re-invoke dbt after a non-zero exit (dbt jobs only)."""

    retries: int
    retry_delay_seconds: float

    @property
    def max_attempts(self) -> int:
        return self.retries + 1


def parse_dbt_retry_policy(config: dict[str, Any]) -> DbtRetryPolicy:
    """Parse ``config.retries`` / ``config.retry_delay_seconds`` (dbt only).

    ``retries`` is the number of *extra* attempts after the first failure
    (default 0 = current no-retry behavior). ``retry_delay_seconds`` is the
    wait between attempts (default ``DEFAULT_DBT_RETRY_DELAY_SECONDS``).
    """
    raw_retries = config.get("retries", DEFAULT_DBT_RETRIES)
    # bool is a subclass of int — reject it explicitly.
    if isinstance(raw_retries, bool) or not isinstance(raw_retries, int):
        raise JobRunError(
            f"dbt job config.retries must be a non-negative int, got {raw_retries!r}"
        )
    if raw_retries < 0:
        raise JobRunError(
            f"dbt job config.retries must be a non-negative int, got {raw_retries!r}"
        )

    raw_delay = config.get("retry_delay_seconds", DEFAULT_DBT_RETRY_DELAY_SECONDS)
    if isinstance(raw_delay, bool) or not isinstance(raw_delay, (int, float)):
        raise JobRunError(
            "dbt job config.retry_delay_seconds must be a non-negative number, "
            f"got {raw_delay!r}"
        )
    if float(raw_delay) < 0:
        raise JobRunError(
            "dbt job config.retry_delay_seconds must be a non-negative number, "
            f"got {raw_delay!r}"
        )
    return DbtRetryPolicy(
        retries=raw_retries,
        retry_delay_seconds=float(raw_delay),
    )


def _combine_dbt_streams(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        combined = stdout
        if not combined.endswith("\n"):
            combined += "\n"
        combined += stderr
        return combined
    return stdout or stderr


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
    policy = parse_dbt_retry_policy(config)
    max_attempts = policy.max_attempts
    now = utc_now_iso()
    with connect(paths.sqlite_path) as conn:
        _insert_running_run(
            conn,
            run_id=run_id,
            job_id=job_id,
            trigger=trigger,
            now=now,
        )

    log_parts: list[str] = []
    last_combined = ""
    last_returncode = 1
    attempts_used = 0

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            time.sleep(policy.retry_delay_seconds)

        attempts_used = attempt
        if max_attempts > 1:
            log_parts.append(f"===== dbt attempt {attempt}/{max_attempts} =====\n")

        try:
            completed = subprocess.run(
                argv,
                cwd=str(paths.dbt_dir),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            # Missing binary is not transient — fail immediately (no further retries).
            finished = utc_now_iso()
            message = f"dbt executable not found: {argv[0]}"
            log_parts.append(f"{message}\n{exc}\n")
            with connect(paths.sqlite_path) as conn:
                _store_run_log(
                    conn,
                    paths=paths,
                    run_id=run_id,
                    output="".join(log_parts),
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

        combined = _combine_dbt_streams(completed.stdout or "", completed.stderr or "")
        last_combined = combined
        last_returncode = completed.returncode
        chunk = combined if combined.endswith("\n") or not combined else combined + "\n"
        log_parts.append(chunk)

        if completed.returncode == 0:
            break

    finished = utc_now_iso()
    if last_returncode == 0:
        status = "succeeded"
        error_message = None
    else:
        status = "failed"
        error_message = _short_dbt_error(last_returncode, last_combined)
        if attempts_used > 1:
            error_message = f"{error_message} (after {attempts_used} attempts)"

    retention_days = 30
    try:
        cfg = load_config(paths)
        raw_days = cfg.get("artifact_retention_days", 30)
        if isinstance(raw_days, int) and raw_days >= 0:
            retention_days = raw_days
    except (OSError, ValueError, FileNotFoundError):
        pass

    with connect(paths.sqlite_path) as conn:
        _store_run_log(
            conn,
            paths=paths,
            run_id=run_id,
            output="".join(log_parts),
            created_at=finished,
        )
        _finish_run(
            conn,
            run_id=run_id,
            status=status,
            error_message=error_message,
            finished_at=finished,
        )
        # Final attempt only: ingest whatever run_results.json dbt left behind.
        ingest_dbt_run_results(
            conn,
            paths=paths,
            run_id=run_id,
            created_at=finished,
            retention_days=retention_days,
        )
        conn.commit()

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
    dbt jobs run ``dbt`` as a sync subprocess, store combined stdout/stderr in
    the ``logs`` table, and ingest ``target/run_results.json`` into ``assets``.
    Optional ``config.retries`` / ``config.retry_delay_seconds`` re-invoke the
    same dbt CLI on non-zero exit (dbt only; python is unchanged).

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
            # Validate argv + retry policy before inserting a run row.
            build_dbt_argv(config)
            parse_dbt_retry_policy(config)
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


def _load_depends_graph(
    sqlite_path: str | Path,
) -> dict[str, list[str]]:
    """Return enabled job name → depends_on list from SQLite."""
    with connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT name, depends_on_json, enabled FROM jobs"
        ).fetchall()

    graph: dict[str, list[str]] = {}
    for row in rows:
        name = str(row["name"])
        if int(row["enabled"]) != 1:
            continue
        raw = row["depends_on_json"] or "[]"
        try:
            deps = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise JobRunError(
                f"job {name!r} has invalid depends_on_json: {exc}"
            ) from exc
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise JobRunError(
                f"job {name!r} depends_on_json must be a JSON array of strings"
            )
        graph[name] = [d.strip() for d in deps if d.strip()]
    return graph


def resolve_dependency_order(
    paths: ProjectPaths,
    job_name: str,
    *,
    sync_first: bool = True,
) -> list[str]:
    """Resolve ``depends_on`` into prerequisites + ``job_name`` (topological order).

    Raises ``JobRunError`` for missing / disabled deps or cycles. Does not insert
    any ``job_runs`` rows.
    """
    if sync_first:
        sync_jobs(paths)
    else:
        bootstrap_sqlite(paths.sqlite_path)

    graph = _load_depends_graph(paths.sqlite_path)
    if job_name not in graph:
        # Distinguish missing vs disabled for a clearer message.
        with connect(paths.sqlite_path) as conn:
            row = conn.execute(
                "SELECT enabled FROM jobs WHERE name = ?",
                (job_name,),
            ).fetchone()
        if row is None:
            raise JobRunError(
                f"job {job_name!r} not found in SQLite "
                "(run `bunsui job sync` or check the name)"
            )
        raise JobRunError(f"job {job_name!r} is disabled")

    # Collect the transitive closure of prerequisites (including job_name).
    needed: set[str] = set()
    stack = [job_name]
    while stack:
        current = stack.pop()
        if current in needed:
            continue
        if current not in graph:
            raise JobRunError(
                f"job {job_name!r} depends on missing or disabled job {current!r}"
            )
        needed.add(current)
        for dep in graph[current]:
            if dep not in graph:
                raise JobRunError(
                    f"job {current!r} depends on missing or disabled job {dep!r}"
                )
            if dep not in needed:
                stack.append(dep)

    # Kahn topological sort on the needed subgraph (stable: preserve depends_on order).
    indegree = {name: 0 for name in needed}
    children: dict[str, list[str]] = {name: [] for name in needed}
    for name in needed:
        for dep in graph[name]:
            if dep not in needed:
                continue
            indegree[name] += 1
            children[dep].append(name)

    # Seed queue with zero-indegree nodes in a deterministic order.
    ready = sorted(name for name, deg in indegree.items() if deg == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                # Insert keeping sorted order among newly ready nodes.
                ready.append(child)
                ready.sort()

    if len(order) != len(needed):
        cyclic = sorted(needed - set(order))
        raise JobRunError(
            f"dependency cycle detected involving: {', '.join(cyclic)}"
        )

    # Ensure the requested leaf is last among ties that Kahn might reorder wrongly:
    # Kahn with sorted ready already yields a valid topo order; leaf may not be last
    # only if something incorrectly depends on it within the subgraph — which would
    # mean we collected jobs that depend on the leaf. We only collect ancestors of
    # the leaf, so the leaf has no dependents in `needed` and is always last-capable.
    # Still assert the leaf appears exactly once.
    if order.count(job_name) != 1:
        raise JobRunError(f"internal error resolving order for {job_name!r}")
    return order


def run_job_chain(
    paths: ProjectPaths,
    job_name: str,
    *,
    sync_first: bool = True,
    trigger: str = "manual",
    wait: bool = True,
    poll_interval: float = DEFAULT_POLL_INTERVAL_S,
    timeout: float = DEFAULT_ASYNC_TIMEOUT_S,
    polled_statuses: list[str] | None = None,
    on_wave: Callable[[int, Sequence[str]], None] | None = None,
    on_result: Callable[[RunResult], None] | None = None,
) -> ChainResult:
    """Run ``job_name`` after its ``depends_on`` prerequisites (parallel waves).

    Jobs whose remaining indegree is zero run together via
    ``ThreadPoolExecutor`` (fan-out). A job starts only after all of its
    ``depends_on`` predecessors in the subgraph have succeeded. Linear chains
    remain one-job-per-wave.

    Upstream jobs always wait for completion (including async python via SQLite
    poll). ``wait`` / ``polled_statuses`` apply only to the leaf job.

    Fail-fast policy: if any job in a wave fails, in-flight siblings in that
    wave are allowed to finish writing ``job_runs``, but no new waves start.
    Validation failures (cycle / missing dep) raise ``JobRunError`` before any
    run row is inserted.
    """
    order = resolve_dependency_order(paths, job_name, sync_first=sync_first)
    graph = _load_depends_graph(paths.sqlite_path)
    needed = set(order)
    succeeded: set[str] = set()
    pending = set(order)
    results: list[RunResult] = []
    wave_num = 0

    while pending:
        ready = sorted(
            name
            for name in pending
            if all(dep in succeeded for dep in graph.get(name, []) if dep in needed)
        )
        if not ready:
            # Should be unreachable after a valid topo resolve unless a bug.
            raise JobRunError(
                f"internal error: no ready jobs while pending "
                f"{', '.join(sorted(pending))}"
            )

        wave_num += 1
        if on_wave is not None:
            on_wave(wave_num, ready)

        def _run_one(step_name: str) -> RunResult:
            is_leaf = step_name == job_name
            return run_job(
                paths,
                step_name,
                sync_first=False,
                trigger=trigger,
                wait=wait if is_leaf else True,
                poll_interval=poll_interval,
                timeout=timeout,
                polled_statuses=polled_statuses if is_leaf else None,
            )

        wave_results: list[RunResult]
        if len(ready) == 1:
            wave_results = [_run_one(ready[0])]
        else:
            with ThreadPoolExecutor(max_workers=len(ready)) as pool:
                futures = {pool.submit(_run_one, name): name for name in ready}
                by_name: dict[str, RunResult] = {}
                for fut in as_completed(futures):
                    result = fut.result()
                    by_name[result.job_name] = result
                wave_results = [by_name[name] for name in ready]

        wave_failed = False
        for result in wave_results:
            results.append(result)
            pending.discard(result.job_name)
            if on_result is not None:
                on_result(result)
            if result.status == "succeeded":
                succeeded.add(result.job_name)
            else:
                wave_failed = True

        if wave_failed:
            break
        if any(r.status == "running" for r in wave_results):
            # Leaf --no-wait: leaf is alone in its wave; stop.
            break

    return ChainResult(order=tuple(order), results=tuple(results))
