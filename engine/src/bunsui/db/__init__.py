"""SQLite bootstrap / migration helpers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bunsui.db.schema import EXPECTED_TABLES, MIGRATIONS, SCHEMA_SQL, SCHEMA_VERSION


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(sqlite_path: Path | str) -> sqlite3.Connection:
    """Open SQLite with foreign keys enabled."""
    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _current_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if row is None:
        return 0
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations"
    ).fetchone()
    return int(row["v"] if isinstance(row, sqlite3.Row) else row[0])


def init_schema(conn: sqlite3.Connection) -> int:
    """Apply schema DDL and any pending migrations. Returns applied version.

    Fresh installs run ``SCHEMA_SQL`` (CREATE IF NOT EXISTS) then record every
    version up to ``SCHEMA_VERSION``. Existing DBs apply ``MIGRATIONS`` for each
    missing version so upgrades stay incremental.
    """
    conn.executescript(SCHEMA_SQL)
    current = _current_schema_version(conn)
    for version in range(current + 1, SCHEMA_VERSION + 1):
        sql = MIGRATIONS.get(version)
        if sql:
            conn.executescript(sql)
        existing = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, utc_now_iso()),
            )
    conn.commit()
    return SCHEMA_VERSION


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]


def verify_schema(conn: sqlite3.Connection) -> None:
    """Raise if expected control-plane tables are missing."""
    tables = set(list_tables(conn))
    missing = [t for t in EXPECTED_TABLES if t not in tables]
    if missing:
        raise RuntimeError(f"SQLite schema missing tables: {', '.join(missing)}")


def bootstrap_sqlite(sqlite_path: Path | str) -> Path:
    """Create/open the control DB and initialize schema. Returns absolute path."""
    path = Path(sqlite_path).resolve()
    with connect(path) as conn:
        init_schema(conn)
        verify_schema(conn)
    return path
