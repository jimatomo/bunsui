"""Cron expression helpers (5-field) shared by job sync and the scheduler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

DEFAULT_SCHEDULE_TIMEZONE = "UTC"


def parse_schedule_fields(
    item: dict[str, Any],
    *,
    source: str,
    job_name: str,
) -> tuple[str | None, str]:
    """Parse optional ``schedule`` / ``timezone`` from a job mapping.

    Accepted forms::

        schedule: "0 * * * *"
        schedule:
          cron: "0 * * * *"
          timezone: Asia/Tokyo   # optional; else top-level timezone or UTC

    Returns ``(cron_or_none, timezone)``. Raises ``ValueError`` with a clear
    location prefix on invalid input.
    """
    loc = f"{source}: job {job_name!r}"
    raw = item.get("schedule")
    top_tz = item.get("timezone")

    if raw is None:
        if top_tz is not None:
            _coerce_timezone(top_tz, loc=loc)  # validate even if unused
        return None, DEFAULT_SCHEDULE_TIMEZONE

    cron: str
    tz_name: str | None = None

    if isinstance(raw, str):
        cron = raw.strip()
    elif isinstance(raw, dict):
        cron_raw = raw.get("cron")
        if not isinstance(cron_raw, str) or not cron_raw.strip():
            raise ValueError(
                f"{loc}: schedule.cron must be a non-empty 5-field cron string"
            )
        cron = cron_raw.strip()
        if "timezone" in raw and raw.get("timezone") is not None:
            tz_name = _coerce_timezone(raw.get("timezone"), loc=f"{loc} schedule")
    else:
        raise ValueError(
            f"{loc}: schedule must be a cron string or a mapping with cron/timezone"
        )

    if not cron:
        raise ValueError(f"{loc}: schedule cron must be a non-empty string")

    validate_cron(cron, loc=loc)

    if tz_name is None and top_tz is not None:
        tz_name = _coerce_timezone(top_tz, loc=loc)
    if tz_name is None:
        tz_name = DEFAULT_SCHEDULE_TIMEZONE
    else:
        _resolve_zone(tz_name, loc=loc)

    return cron, tz_name


def _coerce_timezone(value: Any, *, loc: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{loc}: timezone must be a non-empty IANA name (default UTC)"
        )
    name = value.strip()
    _resolve_zone(name, loc=loc)
    return name


def _resolve_zone(name: str, *, loc: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"{loc}: unknown timezone {name!r} (use an IANA name; default is UTC)"
        ) from exc


def validate_cron(expr: str, *, loc: str = "schedule") -> None:
    """Validate a standard 5-field cron string (minute hour dom month dow)."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(
            f"{loc}: cron must be a standard 5-field expression "
            f"(minute hour day-of-month month day-of-week), got {expr!r} "
            f"with {len(parts)} field(s)"
        )
    if not croniter.is_valid(expr):
        raise ValueError(f"{loc}: invalid cron expression {expr!r}")


def compute_next_due(
    cron: str,
    timezone_name: str,
    after: datetime,
) -> datetime:
    """Return the next fire time strictly after ``after``, as aware UTC."""
    validate_cron(cron)
    tz = _resolve_zone(timezone_name, loc="schedule")
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    after_local = after.astimezone(tz)
    itr = croniter(cron, after_local)
    nxt = itr.get_next(datetime)
    if not isinstance(nxt, datetime):
        raise ValueError(f"croniter returned non-datetime for {cron!r}")
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=tz)
    return nxt.astimezone(timezone.utc).replace(microsecond=0)
