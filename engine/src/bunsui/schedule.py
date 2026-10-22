"""Cron scheduling for jobs (``bunsui schedule list|run``).

Job yaml may declare an optional ``schedule`` (standard 5-field cron) and an
optional ``timezone`` (IANA name; default **UTC**). Sync validates the expression
and upserts ``job_schedules``. The foreground scheduler claims due slots in
SQLite before invoking ``run_job_chain(..., trigger="schedule")``.

Missed-slot policy: **no backfill**. If the scheduler was down past one or more
fire times, a catch-up tick runs the job **at most once**, then advances
``next_due_at`` to the next slot strictly after *now* (intermediate missed
slots are skipped). Claiming the slot (advancing ``next_due_at``) happens in
the same SQLite transaction *before* the run starts, so a restart never
double-fires the same slot.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from bunsui.cron import (
    DEFAULT_SCHEDULE_TIMEZONE,
    compute_next_due,
    validate_cron,
)
from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.paths import ProjectPaths
from bunsui.runner import ChainResult, JobRunError, run_job_chain

logger = logging.getLogger(__name__)

DEFAULT_POLL_SECONDS = 30.0

# Statuses that block a new scheduled run of the same job.
_ACTIVE_RUN_STATUSES = frozenset({"pending", "running"})

# Re-export for callers / tests.
__all__ = [
    "Clock",
    "DEFAULT_POLL_SECONDS",
    "DEFAULT_SCHEDULE_TIMEZONE",
    "FakeClock",
    "JobSchedule",
    "SystemClock",
    "TickResult",
    "compute_next_due",
    "list_schedules",
    "run_scheduler_loop",
    "scheduler_tick",
    "validate_cron",
]


class Clock(Protocol):
    """Injectable clock for deterministic scheduler tests."""

    def now(self) -> datetime:
        """Return an aware UTC datetime."""


class SystemClock:
    """Wall-clock UTC (microseconds stripped for stable ISO storage)."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass
class FakeClock:
    """Mutable clock for tests (no real sleeping)."""

    current: datetime

    def now(self) -> datetime:
        cur = self.current
        if cur.tzinfo is None:
            return cur.replace(tzinfo=timezone.utc)
        return cur.astimezone(timezone.utc)

    def set(self, when: datetime) -> None:
        self.current = when

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self.current = self.now() + timedelta(seconds=seconds)


@dataclass(frozen=True)
class JobSchedule:
    """One enabled job with a cron schedule (from yaml / SQLite)."""

    job_id: str
    job_name: str
    cron: str
    timezone: str
    last_fired_at: str | None
    next_due_at: str


@dataclass(frozen=True)
class TickResult:
    """Outcome of one scheduler poll."""

    fired: tuple[str, ...]
    skipped_overlap: tuple[str, ...]
    results: tuple[ChainResult, ...]


def _parse_iso_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def list_schedules(paths: ProjectPaths) -> list[JobSchedule]:
    """Return enabled jobs that have a ``job_schedules`` row (after bootstrap)."""
    bootstrap_sqlite(paths.sqlite_path)
    with connect(paths.sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT j.id AS job_id, j.name AS job_name,
                   s.cron, s.timezone, s.last_fired_at, s.next_due_at
            FROM job_schedules s
            JOIN jobs j ON j.id = s.job_id
            WHERE j.enabled = 1
            ORDER BY j.name
            """
        ).fetchall()
    return [
        JobSchedule(
            job_id=str(r["job_id"]),
            job_name=str(r["job_name"]),
            cron=str(r["cron"]),
            timezone=str(r["timezone"]),
            last_fired_at=r["last_fired_at"],
            next_due_at=str(r["next_due_at"]),
        )
        for r in rows
    ]


def _job_has_active_run(conn: Any, job_id: str) -> bool:
    placeholders = ",".join("?" * len(_ACTIVE_RUN_STATUSES))
    row = conn.execute(
        f"""
        SELECT 1 FROM job_runs
        WHERE job_id = ? AND status IN ({placeholders})
        LIMIT 1
        """,
        (job_id, *_ACTIVE_RUN_STATUSES),
    ).fetchone()
    return row is not None


def _claim_due_slot(
    conn: Any,
    *,
    job_id: str,
    cron: str,
    timezone_name: str,
    now: datetime,
) -> bool:
    """Atomically claim a due schedule slot. Returns False if no longer due.

    Catch-up: sets ``last_fired_at`` to ``now`` and ``next_due_at`` to the next
    fire **after now** (skips intermediate missed slots).
    """
    now_iso = _iso(now)
    row = conn.execute(
        "SELECT next_due_at FROM job_schedules WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        return False
    next_due = _parse_iso_utc(str(row["next_due_at"]))
    if next_due > now:
        return False
    new_next = compute_next_due(cron, timezone_name, after=now)
    cur = conn.execute(
        """
        UPDATE job_schedules SET
            last_fired_at = ?,
            next_due_at = ?,
            updated_at = ?
        WHERE job_id = ? AND next_due_at = ?
        """,
        (now_iso, _iso(new_next), utc_now_iso(), job_id, row["next_due_at"]),
    )
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True


def scheduler_tick(
    paths: ProjectPaths,
    *,
    clock: Clock | None = None,
    sync_first: bool = True,
    run_chain: Callable[..., ChainResult] | None = None,
) -> TickResult:
    """Poll once: claim due schedules and run them with ``trigger=schedule``.

    Overlapping runs of the same job (pending/running) are skipped and logged;
    their ``next_due_at`` is left unchanged so a later tick can fire after the
    active run finishes.
    """
    from bunsui.jobs import sync_jobs

    clk = clock or SystemClock()
    now = clk.now()
    if sync_first:
        sync_jobs(paths)
    else:
        bootstrap_sqlite(paths.sqlite_path)

    chain_fn = run_chain or run_job_chain
    fired: list[str] = []
    skipped: list[str] = []
    results: list[ChainResult] = []

    schedules = list_schedules(paths)
    due = [s for s in schedules if _parse_iso_utc(s.next_due_at) <= now]

    for sched in due:
        with connect(paths.sqlite_path) as conn:
            if _job_has_active_run(conn, sched.job_id):
                logger.info(
                    "schedule skip %s: previous run still active",
                    sched.job_name,
                )
                skipped.append(sched.job_name)
                continue
            claimed = _claim_due_slot(
                conn,
                job_id=sched.job_id,
                cron=sched.cron,
                timezone_name=sched.timezone,
                now=now,
            )
        if not claimed:
            continue

        logger.info(
            "schedule fire %s (cron=%r tz=%s)",
            sched.job_name,
            sched.cron,
            sched.timezone,
        )
        try:
            result = chain_fn(
                paths,
                sched.job_name,
                sync_first=False,
                trigger="schedule",
            )
        except JobRunError as exc:
            logger.error(
                "schedule run %s failed before start: %s", sched.job_name, exc
            )
            fired.append(sched.job_name)
            continue
        fired.append(sched.job_name)
        results.append(result)

    return TickResult(
        fired=tuple(fired),
        skipped_overlap=tuple(skipped),
        results=tuple(results),
    )


def run_scheduler_loop(
    paths: ProjectPaths,
    *,
    clock: Clock | None = None,
    interval_seconds: float = DEFAULT_POLL_SECONDS,
    once: bool = False,
    sync_first: bool = True,
    sleep_fn: Callable[[float], None] | None = None,
    run_chain: Callable[..., ChainResult] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Sequence[TickResult]:
    """Foreground scheduler loop (or a single tick when ``once=True``).

    ``sleep_fn`` and ``clock`` are injectable so tests never wall-sleep.
    """
    sleeper = sleep_fn or time.sleep
    ticks: list[TickResult] = []
    first = True
    while True:
        if should_stop is not None and should_stop():
            break
        tick = scheduler_tick(
            paths,
            clock=clock,
            sync_first=sync_first and first,
            run_chain=run_chain,
        )
        first = False
        ticks.append(tick)
        if once:
            break
        sleeper(interval_seconds)
        if should_stop is not None and should_stop():
            break
    return ticks
