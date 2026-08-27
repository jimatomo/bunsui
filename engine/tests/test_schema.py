"""Engine unit tests — Phase 0: schema init and project bootstrap."""

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
        assert versions["c"] == 1


def test_init_project_layout(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir()
    paths = init_project(root, name="demo")

    assert paths.config_file.is_file()
    assert paths.sqlite_path.is_file()
    assert paths.duckdb_path.exists()
    assert paths.dbt_dir.is_dir()
    assert (paths.dbt_dir / "dbt_project.yml").is_file()
    assert paths.artifacts_dir.is_dir()
    assert paths.logs_dir.is_dir()

    with connect(paths.sqlite_path) as conn:
        verify_schema(conn)
        # Empty tables are OK in Phase 0
        assert conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"] == 0
