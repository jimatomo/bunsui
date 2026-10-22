"""Engine unit tests for schema init and project bootstrap."""

from __future__ import annotations

from pathlib import Path

from bunsui.db import bootstrap_sqlite, connect, list_tables, verify_schema
from bunsui.db.schema import EXPECTED_TABLES, SCHEMA_VERSION
from bunsui.project import init_project


def test_bootstrap_sqlite_creates_expected_tables(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "control.sqlite"
    bootstrap_sqlite(sqlite_path)
    assert sqlite_path.is_file()

    with connect(sqlite_path) as conn:
        tables = set(list_tables(conn))
        for name in EXPECTED_TABLES:
            assert name in tables
        verify_schema(conn)
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        assert row is not None
        assert row["version"] == SCHEMA_VERSION


def test_bootstrap_sqlite_is_idempotent(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "control.sqlite"
    bootstrap_sqlite(sqlite_path)
    bootstrap_sqlite(sqlite_path)
    with connect(sqlite_path) as conn:
        versions = conn.execute("SELECT COUNT(*) AS c FROM schema_migrations").fetchone()
        assert versions["c"] == SCHEMA_VERSION
        assert "job_schedules" in set(list_tables(conn))


def test_schema_upgrade_adds_job_schedules(tmp_path: Path) -> None:
    """Existing v1 DBs gain job_schedules when bootstrapped with SCHEMA_VERSION=2."""
    from bunsui.db import utc_now_iso

    sqlite_path = tmp_path / "legacy.sqlite"
    with connect(sqlite_path) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                job_type TEXT NOT NULL,
                config_json TEXT,
                depends_on_json TEXT,
                execution_mode TEXT NOT NULL DEFAULT 'sync',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE job_runs (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                trigger TEXT,
                started_at TEXT,
                finished_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE assets (
                id TEXT PRIMARY KEY,
                asset_key TEXT NOT NULL UNIQUE,
                asset_type TEXT,
                status TEXT NOT NULL DEFAULT 'unknown',
                parent_asset_id TEXT,
                last_materialized_at TEXT,
                last_run_id TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE asset_materializations (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                job_run_id TEXT,
                status TEXT NOT NULL,
                materialized_at TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE logs (
                id TEXT PRIMARY KEY,
                job_run_id TEXT NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
                log_kind TEXT NOT NULL DEFAULT 'stdout',
                path TEXT,
                blob_pointer TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE artifacts (
                id TEXT PRIMARY KEY,
                job_run_id TEXT NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                retained_until TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
            (utc_now_iso(),),
        )
        conn.commit()
        assert "job_schedules" not in set(list_tables(conn))

    bootstrap_sqlite(sqlite_path)
    with connect(sqlite_path) as conn:
        assert "job_schedules" in set(list_tables(conn))
        versions = {
            r["version"]
            for r in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        assert 1 in versions
        assert SCHEMA_VERSION in versions


def test_init_project_layout(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir()
    paths = init_project(root, name="demo")

    assert paths.config_file.is_file()
    assert paths.sqlite_path.is_file()
    assert paths.duckdb_path.exists()
    assert paths.dbt_dir.is_dir()
    assert (paths.dbt_dir / "dbt_project.yml").is_file()
    assert (paths.dbt_dir / "models" / "example.sql").is_file()
    assert (paths.dbt_dir / "models" / "schema.yml").is_file()
    assert paths.artifacts_dir.is_dir()
    assert paths.logs_dir.is_dir()

    from bunsui.config import load_config

    cfg = load_config(paths)
    assert "jobs" not in cfg or not cfg.get("jobs")
    assert paths.jobs_dir.is_dir()
    assert (paths.jobs_dir / "example_dbt.yaml").is_file()
    assert (paths.jobs_dir / "example_python.yaml").is_file()

    with connect(paths.sqlite_path) as conn:
        verify_schema(conn)
        # Jobs land in SQLite only after `bunsui job sync`
        assert conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"] == 0
