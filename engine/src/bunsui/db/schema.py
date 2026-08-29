"""SQLite control-plane schema.

Tables cover jobs, assets, runs, logs, and artifacts for the full product.
Some columns and tables are unused until execution and ingest are implemented.
See module docstring in ``bunsui`` for product rules.

Async jobs complete by writing status into ``job_runs`` / ``assets``; the web
API and runners poll SQLite.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

# Product notes embedded next to DDL:
# - assets.parent_asset_id: dbt tests are children of their model asset;
#   a test failure should surface as an error on the parent model.
# - jobs.execution_mode: 'sync' waits for completion; 'async' returns after
#   spawn and completion is detected by polling job_runs.status.
# - artifacts: retain run_results.json (and similar) under a retention window.
# - logs: prefer filesystem path to stdout capture; blob_pointer reserved.

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    -- Dagster-inspired unit of status. asset_key is unique (e.g. model.proj.orders).
    id TEXT PRIMARY KEY,
    asset_key TEXT NOT NULL UNIQUE,
    asset_type TEXT,  -- model | test | seed | snapshot | source | other
    status TEXT NOT NULL DEFAULT 'unknown',
        -- unknown | pending | materializing | materialized | failed | skipped
    parent_asset_id TEXT REFERENCES assets(id) ON DELETE SET NULL,
        -- tests attached to a model are children of that model asset
    last_materialized_at TEXT,
    last_run_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_parent ON assets(parent_asset_id);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);

CREATE TABLE IF NOT EXISTS jobs (
    -- Execution unit: later can run dbt or arbitrary Python.
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    job_type TEXT NOT NULL,  -- dbt | python
    config_json TEXT,  -- command args, callable path, dbt select, etc.
    depends_on_json TEXT,  -- ordered JSON array of job names/ids
    execution_mode TEXT NOT NULL DEFAULT 'sync',  -- sync | async
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_runs (
    -- Run history; status is the polling surface for async completion.
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
        -- pending | running | succeeded | failed | cancelled
    trigger TEXT,  -- manual | schedule | dependency
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_runs_job ON job_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_status ON job_runs(status);

CREATE TABLE IF NOT EXISTS asset_materializations (
    -- Per-run materialization / status events for assets (from run_results.json later).
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    job_run_id TEXT REFERENCES job_runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL,  -- succeeded | failed | skipped
    materialized_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_asset_mats_asset ON asset_materializations(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_mats_run ON asset_materializations(job_run_id);

CREATE TABLE IF NOT EXISTS logs (
    -- Stdout (and related) log pointer tied to a job run for the UI.
    id TEXT PRIMARY KEY,
    job_run_id TEXT NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    log_kind TEXT NOT NULL DEFAULT 'stdout',  -- stdout | stderr | combined
    path TEXT,  -- filesystem path under project logs/
    blob_pointer TEXT,  -- reserved for future remote/object storage
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_logs_run ON logs(job_run_id);

CREATE TABLE IF NOT EXISTS artifacts (
    -- e.g. retained run_results.json path + retention expiry.
    id TEXT PRIMARY KEY,
    job_run_id TEXT NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,  -- run_results_json | manifest | other
    path TEXT NOT NULL,
    retained_until TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(job_run_id);
"""

EXPECTED_TABLES = (
    "schema_migrations",
    "assets",
    "jobs",
    "job_runs",
    "asset_materializations",
    "logs",
    "artifacts",
)
