"""Load and write ``bunsui.yaml`` project configuration."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from bunsui.paths import (
    ARTIFACTS_DIRNAME,
    DBT_DIRNAME,
    DUCKDB_FILENAME,
    LOGS_DIRNAME,
    META_DIRNAME,
    ProjectPaths,
    SQLITE_FILENAME,
)


DEFAULT_CONFIG: dict[str, Any] = {
    "name": "bunsui-project",
    "version": 1,
    # Paths are relative to the project root unless absolute.
    "paths": {
        "meta_dir": META_DIRNAME,
        "sqlite": f"{META_DIRNAME}/{SQLITE_FILENAME}",
        "duckdb": f"{META_DIRNAME}/{DUCKDB_FILENAME}",
        "dbt": DBT_DIRNAME,
        "artifacts": ARTIFACTS_DIRNAME,
        "logs": LOGS_DIRNAME,
    },
    # Retention for run_results.json and similar (days). Enforced by the engine when implemented.
    "artifact_retention_days": 30,
    # Documented defaults for job execution.
    "defaults": {
        "job_execution_mode": "sync",  # sync | async
    },
}


def default_config(name: str = "bunsui-project") -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["name"] = name
    return cfg


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# bunsui project config\n"
        "# Job = execution unit (dbt or Python). Asset = Dagster-style status unit.\n"
        "# Async job completion is detected by polling SQLite status writes.\n"
    )
    path.write_text(header + yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def load_config(paths: ProjectPaths) -> dict[str, Any]:
    if not paths.config_file.is_file():
        raise FileNotFoundError(f"No {paths.config_file.name} in {paths.root}")
    data = yaml.safe_load(paths.config_file.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("bunsui.yaml must be a mapping")
    return data
