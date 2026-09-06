"""Tests for ``type: duckdb_load`` (CSV/Parquet → DuckDB warehouse)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

from bunsui.db import connect
from bunsui.duckdb_load import (
    DuckdbLoadError,
    load_into_duckdb,
    parse_duckdb_load_config,
)
from bunsui.io_paths import resolve_data_path
from bunsui.project import init_project
from bunsui.runner import JobRunError, run_job


def _clear_jobs_dir(root: Path) -> None:
    jobs = root / "jobs"
    if jobs.is_dir():
        shutil.rmtree(jobs)
    jobs.mkdir()


def _write_job_file(root: Path, filename: str, body: object) -> None:
    path = root / "jobs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _write_csv(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_parse_duckdb_load_config_defaults() -> None:
    cfg = parse_duckdb_load_config({"path": "data/a.csv", "table": "orders"})
    assert cfg.path == "data/a.csv"
    assert cfg.table == "orders"
    assert cfg.mode == "replace"
    assert cfg.format is None


def test_parse_duckdb_load_config_rejects_bad_table() -> None:
    with pytest.raises(DuckdbLoadError, match="identifier"):
        parse_duckdb_load_config({"path": "a.csv", "table": "orders;drop"})


def test_resolve_data_path_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(ValueError, match="outside"):
        resolve_data_path(root, "../secret.csv")


def test_load_csv_replace_and_append(tmp_path: Path) -> None:
    root = tmp_path / "load"
    root.mkdir()
    paths = init_project(root, name="load")
    _write_csv(
        root,
        "data/orders.csv",
        "id,customer,amount\n1,alice,10\n2,bob,20\n",
    )
    cfg = parse_duckdb_load_config(
        {"path": "data/orders.csv", "table": "orders", "mode": "replace"}
    )
    result = load_into_duckdb(
        paths.duckdb_path, project_root=paths.root, config=cfg
    )
    assert result.rows_loaded == 2
    assert result.format == "csv"

    conn = duckdb.connect(str(paths.duckdb_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
    finally:
        conn.close()

    _write_csv(
        root,
        "data/orders_more.csv",
        "id,customer,amount\n3,carol,30\n",
    )
    append_cfg = parse_duckdb_load_config(
        {
            "path": "data/orders_more.csv",
            "table": "orders",
            "mode": "append",
            "format": "csv",
        }
    )
    append_result = load_into_duckdb(
        paths.duckdb_path, project_root=paths.root, config=append_cfg
    )
    assert append_result.rows_loaded == 1

    conn = duckdb.connect(str(paths.duckdb_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 3
    finally:
        conn.close()


def test_load_parquet_replace(tmp_path: Path) -> None:
    root = tmp_path / "pq"
    root.mkdir()
    paths = init_project(root, name="pq")
    pq_path = root / "data" / "events.parquet"
    pq_path.parent.mkdir(parents=True, exist_ok=True)
    # Write parquet via DuckDB for a deterministic fixture (no pyarrow dep).
    src = duckdb.connect()
    try:
        src.execute(
            "COPY (SELECT 1 AS id, 'a' AS name UNION ALL SELECT 2, 'b') "
            f"TO '{pq_path}' (FORMAT PARQUET)"
        )
    finally:
        src.close()

    cfg = parse_duckdb_load_config(
        {"path": "data/events.parquet", "table": "events", "mode": "replace"}
    )
    result = load_into_duckdb(
        paths.duckdb_path, project_root=paths.root, config=cfg
    )
    assert result.rows_loaded == 2
    assert result.format == "parquet"

    conn = duckdb.connect(str(paths.duckdb_path))
    try:
        rows = conn.execute("SELECT id, name FROM events ORDER BY id").fetchall()
        assert rows == [(1, "a"), (2, "b")]
    finally:
        conn.close()


def test_run_duckdb_load_job_records_run_log_and_asset(tmp_path: Path) -> None:
    root = tmp_path / "job"
    root.mkdir()
    paths = init_project(root, name="job")
    _clear_jobs_dir(root)
    _write_csv(
        root,
        "data/orders.csv",
        "id,customer,amount\n1,alice,10.5\n2,bob,20.0\n3,carol,7.25\n",
    )
    _write_job_file(
        root,
        "load.yaml",
        {
            "name": "load_orders",
            "type": "duckdb_load",
            "execution_mode": "sync",
            "config": {
                "path": "data/orders.csv",
                "table": "orders",
                "mode": "replace",
            },
        },
    )

    result = run_job(paths, "load_orders")
    assert result.status == "succeeded"
    assert result.error_message is None

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status, finished_at FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "succeeded"
        assert row["finished_at"]

        log = conn.execute(
            "SELECT path FROM logs WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        assert log and log["path"]
        log_text = (paths.root / log["path"]).read_text(encoding="utf-8")
        assert "table=orders" in log_text
        assert "rows_loaded=3" in log_text

        asset = conn.execute(
            "SELECT asset_key, asset_type, status, metadata_json FROM assets "
            "WHERE asset_key = 'table.orders'"
        ).fetchone()
        assert asset is not None
        assert asset["asset_type"] == "table"
        assert asset["status"] == "materialized"
        meta = json.loads(asset["metadata_json"])
        assert meta["rows_loaded"] == 3

        mats = conn.execute(
            "SELECT COUNT(*) AS c FROM asset_materializations WHERE job_run_id = ?",
            (result.run_id,),
        ).fetchone()
        assert mats["c"] == 1

    conn = duckdb.connect(str(paths.duckdb_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 3
    finally:
        conn.close()


def test_run_duckdb_load_missing_file_fails(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    root.mkdir()
    paths = init_project(root, name="missing")
    _clear_jobs_dir(root)
    _write_job_file(
        root,
        "load.yaml",
        {
            "name": "load_missing",
            "type": "duckdb_load",
            "execution_mode": "sync",
            "config": {"path": "data/nope.csv", "table": "orders"},
        },
    )

    result = run_job(paths, "load_missing")
    assert result.status == "failed"
    assert result.error_message is not None
    assert "no files matched" in result.error_message

    with connect(paths.sqlite_path) as conn:
        row = conn.execute(
            "SELECT status FROM job_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        assert row["status"] == "failed"
        assert (
            conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"] == 0
        )


def test_run_duckdb_load_rejects_async_mode(tmp_path: Path) -> None:
    root = tmp_path / "async_bad"
    root.mkdir()
    paths = init_project(root, name="async_bad")
    _clear_jobs_dir(root)
    _write_csv(root, "data/orders.csv", "id\n1\n")
    _write_job_file(
        root,
        "load.yaml",
        {
            "name": "load_async",
            "type": "duckdb_load",
            "execution_mode": "async",
            "config": {"path": "data/orders.csv", "table": "orders"},
        },
    )
    with pytest.raises(JobRunError, match="only support sync"):
        run_job(paths, "load_async")


def test_init_scaffolds_duckdb_load_sample(tmp_path: Path) -> None:
    root = tmp_path / "scaffolded"
    root.mkdir()
    paths = init_project(root, name="scaffolded")
    assert (root / "data" / "orders.csv").is_file()
    assert (root / "jobs" / "example_duckdb_load.yaml").is_file()

    result = run_job(paths, "example_duckdb_load", sync_first=True)
    assert result.status == "succeeded"

    conn = duckdb.connect(str(paths.duckdb_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 3
    finally:
        conn.close()
