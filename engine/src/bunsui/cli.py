"""CLI entrypoint: ``bunsui init`` / ``bunsui version``."""

from __future__ import annotations

from pathlib import Path

import click

from bunsui import __version__
from bunsui.project import init_project


@click.group()
@click.version_option(__version__, prog_name="bunsui")
def main() -> None:
    """bunsui — local data platform (DuckDB + dbt + SQLite)."""


@main.command("init")
@click.argument("path", required=False, type=click.Path())
@click.option("--name", "name", default=None, help="Project name written to bunsui.yaml")
@click.option("--force", is_flag=True, help="Overwrite bunsui.yaml if it exists")
def init_cmd(path: str | None, name: str | None, force: bool) -> None:
    """Scaffold a bunsui project (config, SQLite schema, DuckDB path, dbt stub)."""
    target = Path(path) if path else Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    paths = init_project(target, name=name, force=force)
    click.echo(f"Initialized bunsui project at {paths.root}")
    click.echo(f"  config:   {paths.config_file}")
    click.echo(f"  sqlite:   {paths.sqlite_path}")
    click.echo(f"  duckdb:   {paths.duckdb_path}")
    click.echo(f"  dbt:      {paths.dbt_dir}")
    click.echo(f"  artifacts:{paths.artifacts_dir}")
    click.echo(f"  logs:     {paths.logs_dir}")


@main.command("schema")
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory containing bunsui.yaml",
)
def schema_cmd(project_path: str) -> None:
    """Initialize or verify the SQLite control-plane schema for a project."""
    from bunsui.db import bootstrap_sqlite, list_tables, connect
    from bunsui.paths import resolve_project

    paths = resolve_project(project_path)
    paths.ensure_dirs()
    sqlite_path = bootstrap_sqlite(paths.sqlite_path)
    with connect(sqlite_path) as conn:
        tables = list_tables(conn)
    click.echo(f"SQLite ready: {sqlite_path}")
    click.echo(f"Tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
