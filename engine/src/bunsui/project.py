"""Bootstrap a new bunsui project directory (``bunsui init``)."""

from __future__ import annotations

from pathlib import Path

from bunsui.config import default_config, write_config
from bunsui.db import bootstrap_sqlite
from bunsui.jobs import write_example_job_files
from bunsui.paths import ProjectPaths, resolve_project


DBT_PROJECT_STUB = """\
name: '{name}'
version: '1.0.0'
config-version: 2
profile: '{name}'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"
clean-targets: ["target", "dbt_packages"]
"""

DBT_PROFILES_STUB = """\
# Local DuckDB profile for dbt (execution not wired yet).
{name}:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: '../.bunsui/warehouse.duckdb'
      threads: 4
"""

DBT_MODEL_STUB = """\
-- Example model (dbt run not implemented yet).
select 1 as id
"""

GITKEEP = ""


def init_project(
    path: Path | str | None = None,
    *,
    name: str | None = None,
    force: bool = False,
) -> ProjectPaths:
    """Create project dirs, config, empty DuckDB path reservation, and SQLite schema."""
    paths = resolve_project(path)
    project_name = name or paths.root.name or "bunsui-project"

    if paths.config_file.exists() and not force:
        raise FileExistsError(
            f"{paths.config_file} already exists (pass force=True to overwrite config)"
        )

    paths.ensure_dirs()
    write_config(paths.config_file, default_config(project_name))
    write_example_job_files(paths.jobs_dir)

    # Reserve DuckDB warehouse file path (load/query not implemented yet).
    if not paths.duckdb_path.exists():
        paths.duckdb_path.touch()

    bootstrap_sqlite(paths.sqlite_path)

    # Minimal dbt project stub so the layout is real.
    models_dir = paths.dbt_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (paths.dbt_dir / "dbt_project.yml").write_text(
        DBT_PROJECT_STUB.format(name=project_name.replace("-", "_")),
        encoding="utf-8",
    )
    (paths.dbt_dir / "profiles.yml").write_text(
        DBT_PROFILES_STUB.format(name=project_name.replace("-", "_")),
        encoding="utf-8",
    )
    (models_dir / "example.sql").write_text(DBT_MODEL_STUB, encoding="utf-8")

    (paths.artifacts_dir / ".gitkeep").write_text(GITKEEP, encoding="utf-8")
    (paths.logs_dir / ".gitkeep").write_text(GITKEEP, encoding="utf-8")

    return paths
