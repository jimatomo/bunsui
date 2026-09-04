"""Project layout conventions for a bunsui project directory.

A bunsui project is a directory containing ``bunsui.yaml`` plus reserved paths:

.. code-block:: text

    my-project/
      bunsui.yaml          # project config
      jobs/                # split job declarations (*.yaml); optional inline jobs: too
      .bunsui/
        control.sqlite     # SQLite control plane (jobs / assets / runs)
        warehouse.duckdb   # DuckDB warehouse
      dbt/                 # dbt project directory
      artifacts/           # retained run_results.json etc.
      logs/                # stdout / stderr log files per job run
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONFIG_FILENAME = "bunsui.yaml"
META_DIRNAME = ".bunsui"
SQLITE_FILENAME = "control.sqlite"
DUCKDB_FILENAME = "warehouse.duckdb"
DBT_DIRNAME = "dbt"
ARTIFACTS_DIRNAME = "artifacts"
LOGS_DIRNAME = "logs"
JOBS_DIRNAME = "jobs"


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved filesystem paths for one bunsui project."""

    root: Path

    @property
    def config_file(self) -> Path:
        return self.root / CONFIG_FILENAME

    @property
    def meta_dir(self) -> Path:
        return self.root / META_DIRNAME

    @property
    def sqlite_path(self) -> Path:
        return self.meta_dir / SQLITE_FILENAME

    @property
    def duckdb_path(self) -> Path:
        return self.meta_dir / DUCKDB_FILENAME

    @property
    def dbt_dir(self) -> Path:
        return self.root / DBT_DIRNAME

    @property
    def artifacts_dir(self) -> Path:
        return self.root / ARTIFACTS_DIRNAME

    @property
    def logs_dir(self) -> Path:
        return self.root / LOGS_DIRNAME

    @property
    def jobs_dir(self) -> Path:
        return self.root / JOBS_DIRNAME

    def ensure_dirs(self) -> None:
        """Create directories that the engine expects to exist."""
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.dbt_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


def resolve_project(path: Path | str | None = None) -> ProjectPaths:
    """Resolve project root from ``path`` or the current working directory."""
    root = Path(path).resolve() if path is not None else Path.cwd().resolve()
    return ProjectPaths(root=root)
