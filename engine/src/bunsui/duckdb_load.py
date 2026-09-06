"""Load local CSV / Parquet files into the project DuckDB warehouse.

Job type ``duckdb_load`` (sync only). Config::

    path: data/orders.csv   # relative file or glob
    table: orders
    mode: replace | append  # default replace
    format: csv | parquet   # optional; inferred from extension
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import duckdb

from bunsui.io_paths import ResolvedDataPath, resolve_data_path

LoadFormat = Literal["csv", "parquet"]
LoadMode = Literal["replace", "append"]

ALLOWED_FORMATS = frozenset({"csv", "parquet"})
ALLOWED_MODES = frozenset({"replace", "append"})
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CSV_SUFFIXES = frozenset({".csv", ".tsv", ".txt"})
_PARQUET_SUFFIXES = frozenset({".parquet", ".pq"})


@dataclass(frozen=True)
class DuckdbLoadConfig:
    """Validated ``duckdb_load`` job config."""

    path: str
    table: str
    mode: LoadMode
    format: LoadFormat | None  # None = auto-detect from matched files


@dataclass(frozen=True)
class DuckdbLoadResult:
    """Outcome of one warehouse load."""

    table: str
    mode: LoadMode
    format: LoadFormat
    path: str
    rows_loaded: int
    files_matched: int


class DuckdbLoadError(Exception):
    """Config or load failure surfaced to the job runner."""


def parse_duckdb_load_config(config: dict[str, Any]) -> DuckdbLoadConfig:
    """Validate job ``config`` for ``type: duckdb_load``."""
    path = config.get("path")
    if not isinstance(path, str) or not path.strip():
        raise DuckdbLoadError("duckdb_load config.path is required (file or glob)")
    path = path.strip()

    table = config.get("table")
    if not isinstance(table, str) or not table.strip():
        raise DuckdbLoadError("duckdb_load config.table is required")
    table = table.strip()
    if not _TABLE_NAME_RE.match(table):
        raise DuckdbLoadError(
            "duckdb_load config.table must be a simple identifier "
            f"(letters, digits, underscore), got {table!r}"
        )

    mode_raw = config.get("mode", "replace")
    if mode_raw not in ALLOWED_MODES:
        raise DuckdbLoadError(
            f"duckdb_load config.mode must be one of {sorted(ALLOWED_MODES)}, "
            f"got {mode_raw!r}"
        )
    mode: LoadMode = "append" if mode_raw == "append" else "replace"

    format_raw = config.get("format")
    detected: LoadFormat | None = None
    if format_raw is not None and format_raw != "":
        if format_raw not in ALLOWED_FORMATS:
            raise DuckdbLoadError(
                f"duckdb_load config.format must be one of {sorted(ALLOWED_FORMATS)}, "
                f"got {format_raw!r}"
            )
        detected = "csv" if format_raw == "csv" else "parquet"

    return DuckdbLoadConfig(path=path, table=table, mode=mode, format=detected)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def detect_format(
    files: Sequence[Path],
    explicit: LoadFormat | None,
) -> LoadFormat:
    """Infer csv/parquet from file suffixes unless ``explicit`` is set."""
    if explicit is not None:
        return explicit
    if not files:
        raise DuckdbLoadError("cannot auto-detect format: no files matched")
    kinds: set[LoadFormat] = set()
    for path in files:
        suffix = path.suffix.lower()
        if suffix in _CSV_SUFFIXES:
            kinds.add("csv")
        elif suffix in _PARQUET_SUFFIXES:
            kinds.add("parquet")
        else:
            raise DuckdbLoadError(
                f"cannot auto-detect format for {path.name!r}; "
                "set config.format to csv or parquet"
            )
    if len(kinds) != 1:
        raise DuckdbLoadError(
            "matched files mix csv and parquet; set config.format explicitly"
        )
    return next(iter(kinds))


def _read_relation_sql(fmt: LoadFormat) -> str:
    if fmt == "csv":
        return "read_csv_auto(?)"
    return "read_parquet(?)"


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        LIMIT 1
        """,
        [table],
    ).fetchone()
    return row is not None


def load_into_duckdb(
    duckdb_path: Path | str,
    *,
    project_root: Path,
    config: DuckdbLoadConfig,
) -> DuckdbLoadResult:
    """Open the warehouse and load ``config.path`` into ``config.table``."""
    try:
        resolved = resolve_data_path(project_root, config.path)
    except ValueError as exc:
        raise DuckdbLoadError(str(exc)) from exc

    if not resolved.matched_files:
        raise DuckdbLoadError(
            f"no files matched path {config.path!r} under {project_root}"
        )

    fmt = detect_format(resolved.matched_files, config.format)
    relation = _read_relation_sql(fmt)
    quoted = _quote_ident(config.table)
    path_arg = resolved.duckdb_path

    conn = duckdb.connect(str(duckdb_path))
    try:
        if config.mode == "replace":
            conn.execute(
                f"CREATE OR REPLACE TABLE {quoted} AS SELECT * FROM {relation}",
                [path_arg],
            )
            rows_loaded = int(
                conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            )
        else:
            if _table_exists(conn, config.table):
                before = int(
                    conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                )
                conn.execute(
                    f"INSERT INTO {quoted} BY NAME SELECT * FROM {relation}",
                    [path_arg],
                )
                after = int(
                    conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                )
                rows_loaded = after - before
            else:
                conn.execute(
                    f"CREATE TABLE {quoted} AS SELECT * FROM {relation}",
                    [path_arg],
                )
                rows_loaded = int(
                    conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                )
    except DuckdbLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface DuckDB errors to the operator
        raise DuckdbLoadError(f"DuckDB load failed: {exc}") from exc
    finally:
        conn.close()

    return DuckdbLoadResult(
        table=config.table,
        mode=config.mode,
        format=fmt,
        path=resolved.display_path,
        rows_loaded=rows_loaded,
        files_matched=len(resolved.matched_files),
    )


def format_load_log(result: DuckdbLoadResult) -> str:
    """Short operator-facing log for ``logs/`` + UI."""
    return (
        f"duckdb_load table={result.table} mode={result.mode} format={result.format}\n"
        f"path={result.path} files={result.files_matched} rows_loaded={result.rows_loaded}\n"
    )


def upsert_load_asset(
    conn: Any,
    *,
    result: DuckdbLoadResult,
    run_id: str,
    created_at: str,
) -> str:
    """Upsert one ``table.<name>`` asset + materialization row. Returns asset_key."""
    asset_key = f"table.{result.table}"
    metadata_json = json.dumps(
        {
            "table": result.table,
            "mode": result.mode,
            "format": result.format,
            "path": result.path,
            "rows_loaded": result.rows_loaded,
            "files_matched": result.files_matched,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    existing = conn.execute(
        "SELECT id FROM assets WHERE asset_key = ?",
        (asset_key,),
    ).fetchone()

    if existing is not None:
        asset_id = str(existing["id"])
        conn.execute(
            """
            UPDATE assets SET
                asset_type = 'table',
                status = 'materialized',
                last_materialized_at = ?,
                last_run_id = ?,
                metadata_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (created_at, run_id, metadata_json, created_at, asset_id),
        )
    else:
        asset_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO assets (
                id, asset_key, asset_type, status, parent_asset_id,
                last_materialized_at, last_run_id, metadata_json,
                created_at, updated_at
            ) VALUES (?, ?, 'table', 'materialized', NULL, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                asset_key,
                created_at,
                run_id,
                metadata_json,
                created_at,
                created_at,
            ),
        )

    conn.execute(
        """
        INSERT INTO asset_materializations (
            id, asset_id, job_run_id, status, materialized_at,
            metadata_json, created_at
        ) VALUES (?, ?, ?, 'succeeded', ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            asset_id,
            run_id,
            created_at,
            metadata_json,
            created_at,
        ),
    )
    return asset_key


__all__ = [
    "DuckdbLoadConfig",
    "DuckdbLoadError",
    "DuckdbLoadResult",
    "detect_format",
    "format_load_log",
    "load_into_duckdb",
    "parse_duckdb_load_config",
    "upsert_load_asset",
    "ResolvedDataPath",
    "resolve_data_path",
]
