"""Tests for cron validation, due computation, and the foreground scheduler."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from bunsui.cron import compute_next_due, parse_schedule_fields, validate_cron
from bunsui.db import connect
from bunsui.jobs import load_declared_jobs, parse_jobs, sync_jobs
from bunsui.project import init_project
from bunsui.runner import ChainResult, RunResult
from bunsui.schedule import FakeClock, list_schedules, scheduler_tick


def _clear_jobs_dir(root: Path) -> None:
    jobs = root / "jobs"
    if jobs.is_dir():
        for p in jobs.iterdir():
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil

                shutil.rmtree(p)


def _write_job(root: Path, filename: str, body: object) -> None:
    path = root / "jobs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_validate_cron_accepts_five_fields() -> None:
    validate_cron("*/5 * * * *")
    validate_cron("0 9 * * 1-5")


def test_validate_cron_rejects_bad() -> None:
    with pytest.raises(ValueError, match="5-field"):
        validate_cron("0 * * *")
    with pytest.raises(ValueError, match="5-field"):
        validate_cron("0 0 * * * *")  # seconds form
    with pytest.raises(ValueError, match="invalid cron"):
        validate_cron("99 99 99 99 99")


def test_parse_schedule_string_defaults_utc() -> None:
    cron, tz = parse_schedule_fields(
        {"name": "j", "type": "python", "schedule": "0 * * * *"},
        source="jobs/j.yaml",
        job_name="j",
    )
    assert cron == "0 * * * *"
    assert tz == "UTC"


def test_parse_schedule_mapping_with_timezone() -> None:
    cron, tz = parse_schedule_fields(
        {
            "schedule": {"cron": "30 8 * * *", "timezone": "Asia/Tokyo"},
        },
        source="jobs/j.yaml",
        job_name="j",
    )
    assert cron == "30 8 * * *"
    assert tz == "Asia/Tokyo"


def test_parse_schedule_rejects_unknown_timezone() -> None:
    with pytest.raises(ValueError, match="unknown timezone"):
        parse_schedule_fields(
            {"schedule": "0 * * * *", "timezone": "Not/AZone"},
            source="x",
            job_name="j",
        )


def test_parse_jobs_rejects_invalid_schedule() -> None:
    with pytest.raises(ValueError, match="invalid cron|5-field"):
        parse_jobs(
            {
                "jobs": [
                    {
                        "name": "bad",
                        "type": "python",
                        "schedule": "not a cron",
                        "config": {"callable": "m:f"},
                    }
                ]
            }
        )


def test_compute_next_due_hourly_utc() -> None:
    after = datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)
    nxt = compute_next_due("0 * * * *", "UTC", after=after)
    assert nxt == datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)


def test_sync_persists_schedule_and_next_due(tmp_path: Path) -> None:
    root = tmp_path / "sched"
    root.mkdir()
    paths = init_project(root, name="sched")
    _clear_jobs_dir(root)
    _write_job(
        root,
        "hourly.yaml",
        {
            "name": "hourly",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": [],
            "schedule": "0 * * * *",
            "config": {"callable": "sample:main"},
        },
    )
    sync_jobs(paths)
    decls = load_declared_jobs(paths)
    assert decls[0].schedule == "0 * * * *"
    assert decls[0].schedule_timezone == "UTC"

    rows = list_schedules(paths)
    assert len(rows) == 1
    assert rows[0].job_name == "hourly"
    assert rows[0].cron == "0 * * * *"
    assert rows[0].last_fired_at is None
    assert rows[0].next_due_at  # future ISO


def test_sync_removes_schedule_when_cleared(tmp_path: Path) -> None:
    root = tmp_path / "clear"
    root.mkdir()
    paths = init_project(root, name="clear")
    _clear_jobs_dir(root)
    body = {
        "name": "hourly",
        "type": "python",
        "depends_on": [],
        "schedule": "0 * * * *",
        "config": {"callable": "sample:main"},
    }
    _write_job(root, "hourly.yaml", body)
    sync_jobs(paths)
    assert len(list_schedules(paths)) == 1

    del body["schedule"]
    _write_job(root, "hourly.yaml", body)
    sync_jobs(paths)
    assert list_schedules(paths) == []


def test_no_double_fire_across_restart(tmp_path: Path) -> None:
    root = tmp_path / "restart"
    root.mkdir()
    paths = init_project(root, name="restart")
    _clear_jobs_dir(root)
    _write_job(
        root,
        "tick.yaml",
        {
            "name": "tick",
            "type": "python",
            "depends_on": [],
            "schedule": "* * * * *",
            "config": {"callable": "sample:main"},
        },
    )
    sync_jobs(paths)

    # Make the job due in the past.
    past = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    with connect(paths.sqlite_path) as conn:
        conn.execute(
            "UPDATE job_schedules SET next_due_at = ?",
            (past.isoformat(),),
        )
        conn.commit()

    clock = FakeClock(past + timedelta(minutes=2))
    calls: list[str] = []

    def fake_chain(paths_arg, job_name, **kwargs):  # noqa: ANN001
        calls.append(job_name)
        assert kwargs.get("trigger") == "schedule"
        return ChainResult(
            order=(job_name,),
            results=(
                RunResult(run_id="r1", job_name=job_name, status="succeeded"),
            ),
        )

    t1 = scheduler_tick(
        paths, clock=clock, sync_first=False, run_chain=fake_chain
    )
    assert t1.fired == ("tick",)
    assert len(calls) == 1

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT last_fired_at, next_due_at FROM job_schedules"
        ).fetchone()
        next_due = datetime.fromisoformat(row["next_due_at"])
        assert next_due > clock.now()
        last = row["last_fired_at"]

    # Simulate process restart at the same clock instant: must not fire again.
    t2 = scheduler_tick(
        paths, clock=clock, sync_first=False, run_chain=fake_chain
    )
    assert t2.fired == ()
    assert len(calls) == 1

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT last_fired_at, next_due_at FROM job_schedules"
        ).fetchone()
        assert row["last_fired_at"] == last


def test_catchup_runs_at_most_once(tmp_path: Path) -> None:
    """Missed slots are not backfilled — one fire, then next future slot."""
    root = tmp_path / "catchup"
    root.mkdir()
    paths = init_project(root, name="catchup")
    _clear_jobs_dir(root)
    _write_job(
        root,
        "hourly.yaml",
        {
            "name": "hourly",
            "type": "python",
            "depends_on": [],
            "schedule": "0 * * * *",
            "config": {"callable": "sample:main"},
        },
    )
    sync_jobs(paths)

    # Overdue by several hours.
    overdue = datetime(2024, 6, 1, 5, 0, tzinfo=timezone.utc)
    now = datetime(2024, 6, 1, 10, 30, tzinfo=timezone.utc)
    with connect(paths.sqlite_path) as conn:
        conn.execute(
            "UPDATE job_schedules SET next_due_at = ?",
            (overdue.isoformat(),),
        )
        conn.commit()

    calls: list[str] = []

    def fake_chain(paths_arg, job_name, **kwargs):  # noqa: ANN001
        calls.append(job_name)
        return ChainResult(
            order=(job_name,),
            results=(
                RunResult(run_id="r1", job_name=job_name, status="succeeded"),
            ),
        )

    tick = scheduler_tick(
        paths,
        clock=FakeClock(now),
        sync_first=False,
        run_chain=fake_chain,
    )
    assert tick.fired == ("hourly",)
    assert len(calls) == 1

    with connect(paths.sqlite_path) as conn:
        next_due = datetime.fromisoformat(
            conn.execute("SELECT next_due_at FROM job_schedules").fetchone()[
                "next_due_at"
            ]
        )
    # Next slot after *now* (10:30) for hourly-at-:00 is 11:00 — not 06:00..10:00.
    assert next_due == datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)


def test_overlap_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = tmp_path / "overlap"
    root.mkdir()
    paths = init_project(root, name="overlap")
    _clear_jobs_dir(root)
    _write_job(
        root,
        "busy.yaml",
        {
            "name": "busy",
            "type": "python",
            "depends_on": [],
            "schedule": "* * * * *",
            "config": {"callable": "sample:main"},
        },
    )
    sync_jobs(paths)

    past = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    with connect(paths.sqlite_path) as conn:
        job_id = conn.execute(
            "SELECT id FROM jobs WHERE name = 'busy'"
        ).fetchone()["id"]
        conn.execute(
            "UPDATE job_schedules SET next_due_at = ?",
            (past.isoformat(),),
        )
        now = past.isoformat()
        conn.execute(
            """
            INSERT INTO job_runs (
                id, job_id, status, trigger, started_at, finished_at,
                error_message, created_at, updated_at
            ) VALUES ('run-active', ?, 'running', 'manual', ?, NULL, NULL, ?, ?)
            """,
            (job_id, now, now, now),
        )
        conn.commit()

    calls: list[str] = []

    def fake_chain(paths_arg, job_name, **kwargs):  # noqa: ANN001
        calls.append(job_name)
        return ChainResult(
            order=(job_name,),
            results=(
                RunResult(run_id="x", job_name=job_name, status="succeeded"),
            ),
        )

    with caplog.at_level(logging.INFO, logger="bunsui.schedule"):
        tick = scheduler_tick(
            paths,
            clock=FakeClock(past + timedelta(minutes=1)),
            sync_first=False,
            run_chain=fake_chain,
        )

    assert tick.skipped_overlap == ("busy",)
    assert tick.fired == ()
    assert calls == []
    # next_due unchanged so a later tick can fire after the active run ends.
    with connect(paths.sqlite_path) as conn:
        next_due = conn.execute(
            "SELECT next_due_at FROM job_schedules"
        ).fetchone()["next_due_at"]
    assert next_due == past.isoformat()
    assert any("skip" in r.message for r in caplog.records)


def test_trigger_schedule_recorded(tmp_path: Path) -> None:
    root = tmp_path / "trig"
    root.mkdir()
    paths = init_project(root, name="trig")
    _clear_jobs_dir(root)
    # Use the sample callable that ships with init.
    _write_job(
        root,
        "scheduled.yaml",
        {
            "name": "scheduled",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": [],
            "schedule": "* * * * *",
            "config": {"callable": "sample:main"},
        },
    )
    sync_jobs(paths)
    past = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    with connect(paths.sqlite_path) as conn:
        conn.execute(
            "UPDATE job_schedules SET next_due_at = ?",
            (past.isoformat(),),
        )
        conn.commit()

    tick = scheduler_tick(
        paths,
        clock=FakeClock(past + timedelta(seconds=30)),
        sync_first=False,
    )
    assert tick.fired == ("scheduled",)
    assert tick.results[0].status == "succeeded"

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT r.trigger, r.status, j.name
            FROM job_runs r JOIN jobs j ON j.id = r.job_id
            ORDER BY r.created_at DESC LIMIT 1
            """
        ).fetchone()
    assert row["name"] == "scheduled"
    assert row["trigger"] == "schedule"
    assert row["status"] == "succeeded"
