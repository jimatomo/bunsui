"""CLI entrypoint: ``bunsui init`` / ``job`` / ``schedule`` / ``schema``."""

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
    click.echo(
        "Next: edit jobs/, then `bunsui job sync` / "
        "`bunsui job run example_python --project …` "
        "(walks example_dbt → example_python; use --no-deps for one job)"
    )


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


@main.group("job")
def job_group() -> None:
    """Manage and run jobs (yaml → SQLite → python / dbt run)."""


@job_group.command("sync")
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory containing bunsui.yaml",
)
def job_sync_cmd(project_path: str) -> None:
    """Upsert jobs from yaml into SQLite (idempotent; does not run jobs)."""
    from bunsui.jobs import sync_jobs
    from bunsui.paths import resolve_project

    paths = resolve_project(project_path)
    result = sync_jobs(paths)
    click.echo(
        f"Jobs synced for {paths.root}: "
        f"created={result.created} updated={result.updated} disabled={result.disabled}"
    )


@job_group.command("run")
@click.argument("job_name")
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory containing bunsui.yaml",
)
@click.option(
    "--no-sync",
    is_flag=True,
    help="Skip yaml→SQLite sync before running (job must already exist)",
)
@click.option(
    "--no-wait",
    is_flag=True,
    help="For async leaf jobs: start the child and return while status is still running",
)
@click.option(
    "--no-deps",
    is_flag=True,
    help="Run only the named job (do not walk depends_on)",
)
def job_run_cmd(
    job_name: str,
    project_path: str,
    no_sync: bool,
    no_wait: bool,
    no_deps: bool,
) -> None:
    """Run a job (python or dbt), walking ``depends_on`` unless ``--no-deps``.

    Prerequisites run in topological waves; independent siblings fan out in
    parallel. A wave failure waits for in-flight siblings to finish writing
    ``job_runs``, then skips further waves. Python sync jobs run in-process;
    async jobs spawn a child and complete when SQLite status leaves ``running``
    (poll). Upstream async jobs always wait. dbt jobs run as a sync subprocess
    and store combined stdout/stderr under ``logs/``. Syncs yaml first unless
    ``--no-sync``.
    """
    from bunsui.paths import resolve_project
    from bunsui.runner import (
        JobRunError,
        RunResult,
        resolve_dependency_order,
        run_job,
        run_job_chain,
    )

    paths = resolve_project(project_path)
    try:
        if no_deps:
            result = run_job(
                paths, job_name, sync_first=not no_sync, wait=not no_wait
            )
            _echo_run_result(result)
            return

        order = resolve_dependency_order(
            paths, job_name, sync_first=not no_sync
        )
        if len(order) > 1:
            click.echo(f"Running chain: {' → '.join(order)}")

        def on_wave(wave_num: int, jobs: object) -> None:
            names = [str(n) for n in jobs]  # type: ignore[union-attr]
            if len(names) > 1:
                click.echo(f"Wave {wave_num}: parallel {' + '.join(names)}")

        completed: list[str] = []
        failed: RunResult | None = None
        started_running: RunResult | None = None

        def on_result(result: RunResult) -> None:
            nonlocal failed, started_running
            if result.status == "running":
                started_running = result
                return
            if result.status == "succeeded":
                completed.append(result.job_name)
                click.echo(
                    f"Job {result.job_name!r} succeeded (run_id={result.run_id})"
                )
                return
            failed = result

        chain = run_job_chain(
            paths,
            job_name,
            sync_first=False,
            wait=not no_wait,
            on_wave=on_wave,
            on_result=on_result,
        )

        if started_running is not None:
            click.echo(
                f"Job {started_running.job_name!r} started "
                f"(run_id={started_running.run_id}, status=running)"
            )
            return

        if failed is not None:
            remaining = [
                name
                for name in chain.order
                if name not in completed and name != failed.job_name
            ]
            suffix = f"; skipped: {', '.join(remaining)}" if remaining else ""
            raise click.ClickException(
                f"Job {failed.job_name!r} failed (run_id={failed.run_id}): "
                f"{failed.error_message}{suffix}"
            )
    except JobRunError as exc:
        raise click.ClickException(str(exc)) from exc



@job_group.command("retry")
@click.argument("run_id")
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory containing bunsui.yaml",
)
def job_retry_cmd(run_id: str, project_path: str) -> None:
    """Re-run native ``dbt retry`` for a prior dbt ``job_runs`` id.

    Creates a **new** job_runs row (trigger=retry). Restores ``run_results.json``
    from the ArtifactStore for the prior run, then invokes ``dbt retry`` (not the
    original build/run argv). Additional attempts honor the job's ``config.retries``.
    Does not mutate the prior run. Python jobs are not supported.
    """
    from bunsui.paths import resolve_project
    from bunsui.runner import JobRunError, retry_job_run

    paths = resolve_project(project_path)
    try:
        result = retry_job_run(paths, run_id)
    except JobRunError as exc:
        raise click.ClickException(str(exc)) from exc
    _echo_run_result(result)


def _echo_run_result(result: object) -> None:
    from bunsui.runner import RunResult

    assert isinstance(result, RunResult)
    if result.status == "running":
        click.echo(
            f"Job {result.job_name!r} started "
            f"(run_id={result.run_id}, status=running)"
        )
        return
    if result.status == "succeeded":
        click.echo(f"Job {result.job_name!r} succeeded (run_id={result.run_id})")
        return
    raise click.ClickException(
        f"Job {result.job_name!r} failed (run_id={result.run_id}): "
        f"{result.error_message}"
    )


@main.group("schedule")
def schedule_group() -> None:
    """Foreground cron scheduler (list / run)."""


@schedule_group.command("list")
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory containing bunsui.yaml",
)
@click.option(
    "--no-sync",
    is_flag=True,
    help="Skip yaml→SQLite sync before listing",
)
def schedule_list_cmd(project_path: str, no_sync: bool) -> None:
    """List jobs with a cron schedule and their next fire times (UTC).

    Syncs yaml first unless ``--no-sync``. Default timezone for schedules without
    an explicit ``timezone`` is UTC. Missed slots are not backfilled: see
    ``bunsui schedule run``.
    """
    from bunsui.jobs import sync_jobs
    from bunsui.paths import resolve_project
    from bunsui.schedule import list_schedules

    paths = resolve_project(project_path)
    if not no_sync:
        sync_jobs(paths)
    rows = list_schedules(paths)
    if not rows:
        click.echo("No scheduled jobs.")
        return
    click.echo(
        f"{'JOB':<28} {'CRON':<20} {'TZ':<16} {'NEXT_DUE_UTC':<25} LAST_FIRED_UTC"
    )
    for s in rows:
        last = s.last_fired_at or "-"
        click.echo(
            f"{s.job_name:<28} {s.cron:<20} {s.timezone:<16} "
            f"{s.next_due_at:<25} {last}"
        )


@schedule_group.command("run")
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory containing bunsui.yaml",
)
@click.option(
    "--once",
    is_flag=True,
    help="Poll once and exit (no sleep loop)",
)
@click.option(
    "--interval",
    "interval_seconds",
    type=float,
    default=30.0,
    show_default=True,
    help="Seconds between polls when looping",
)
@click.option(
    "--no-sync",
    is_flag=True,
    help="Skip yaml→SQLite sync before the first tick",
)
def schedule_run_cmd(
    project_path: str,
    once: bool,
    interval_seconds: float,
    no_sync: bool,
) -> None:
    """Run the foreground scheduler: fire due jobs with ``trigger=schedule``.

    Persists ``last_fired_at`` / ``next_due_at`` in SQLite so a restart never
    double-fires the same slot. Missed slots while down are **not** backfilled:
    on catch-up a job runs at most once, then ``next_due`` jumps to the next
    future slot. A job with a still-active run (pending/running) is skipped.
    """
    from bunsui.paths import resolve_project
    from bunsui.schedule import run_scheduler_loop

    if interval_seconds <= 0:
        raise click.ClickException("--interval must be positive")

    paths = resolve_project(project_path)
    click.echo(
        f"Scheduler starting for {paths.root} "
        f"({'once' if once else f'interval={interval_seconds}s'})"
    )

    ticks = run_scheduler_loop(
        paths,
        interval_seconds=interval_seconds,
        once=once,
        sync_first=not no_sync,
    )
    for tick in ticks:
        for name in tick.skipped_overlap:
            click.echo(f"skip {name!r}: previous run still active")
        for name in tick.fired:
            click.echo(f"fired {name!r}")
        for result in tick.results:
            if result.status == "failed":
                click.echo(
                    f"  chain {result.job_name!r} failed: {result.error_message}",
                    err=True,
                )
            elif result.status == "succeeded":
                click.echo(f"  chain {result.job_name!r} succeeded")
    if once and ticks and not ticks[0].fired and not ticks[0].skipped_overlap:
        click.echo("No jobs due.")


if __name__ == "__main__":
    main()
