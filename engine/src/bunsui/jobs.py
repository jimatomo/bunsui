"""Declare jobs in ``bunsui.yaml`` and materialize them into SQLite.

This module only syncs declarations into the ``jobs`` table. It does not run
dbt, invoke Python callables, or write ``job_runs``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.paths import ProjectPaths

ALLOWED_JOB_TYPES = frozenset({"dbt", "python"})
ALLOWED_EXECUTION_MODES = frozenset({"sync", "async"})


@dataclass(frozen=True)
class JobDecl:
    """One job declaration from ``bunsui.yaml``."""

    name: str
    job_type: str
    execution_mode: str
    depends_on: list[str]
    config: dict[str, Any]


@dataclass(frozen=True)
class SyncResult:
    """Counts from a single ``job sync`` pass."""

    created: int
    updated: int
    disabled: int

    @property
    def upserted(self) -> int:
        return self.created + self.updated


def parse_jobs(config: dict[str, Any]) -> list[JobDecl]:
    """Parse and validate the ``jobs:`` list from a loaded config mapping."""
    raw = config.get("jobs", [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("bunsui.yaml: jobs must be a list")

    seen: set[str] = set()
    jobs: list[JobDecl] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"bunsui.yaml: jobs[{i}] must be a mapping")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"bunsui.yaml: jobs[{i}] requires a non-empty name")
        name = name.strip()
        if name in seen:
            raise ValueError(f"bunsui.yaml: duplicate job name {name!r}")
        seen.add(name)

        job_type = item.get("type")
        if job_type not in ALLOWED_JOB_TYPES:
            raise ValueError(
                f"bunsui.yaml: job {name!r} type must be one of "
                f"{sorted(ALLOWED_JOB_TYPES)}, got {job_type!r}"
            )

        defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
        mode = item.get("execution_mode", defaults.get("job_execution_mode", "sync"))
        if mode not in ALLOWED_EXECUTION_MODES:
            raise ValueError(
                f"bunsui.yaml: job {name!r} execution_mode must be one of "
                f"{sorted(ALLOWED_EXECUTION_MODES)}, got {mode!r}"
            )

        depends_on = item.get("depends_on") or []
        if not isinstance(depends_on, list) or not all(
            isinstance(d, str) and d.strip() for d in depends_on
        ):
            raise ValueError(
                f"bunsui.yaml: job {name!r} depends_on must be a list of names"
            )
        depends_on = [d.strip() for d in depends_on]

        config_obj = item.get("config") or {}
        if not isinstance(config_obj, dict):
            raise ValueError(f"bunsui.yaml: job {name!r} config must be a mapping")

        jobs.append(
            JobDecl(
                name=name,
                job_type=str(job_type),
                execution_mode=str(mode),
                depends_on=depends_on,
                config=dict(config_obj),
            )
        )

    known = {j.name for j in jobs}
    for job in jobs:
        for dep in job.depends_on:
            if dep not in known:
                raise ValueError(
                    f"bunsui.yaml: job {job.name!r} depends_on unknown job {dep!r}"
                )
            if dep == job.name:
                raise ValueError(f"bunsui.yaml: job {job.name!r} cannot depend on itself")

    return jobs


def example_jobs() -> list[dict[str, Any]]:
    """Sample job declarations written by ``bunsui init``."""
    return [
        {
            "name": "example_dbt",
            "type": "dbt",
            "execution_mode": "sync",
            "depends_on": [],
            "config": {
                "command": "run",
                "select": "example",
            },
        },
        {
            "name": "example_python",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["example_dbt"],
            "config": {
                "callable": "my_module:main",
            },
        },
    ]


def sync_jobs(paths: ProjectPaths, config: dict[str, Any] | None = None) -> SyncResult:
    """Upsert yaml jobs into SQLite; disable rows no longer listed.

    Idempotent: re-running with the same yaml yields the same enabled rows.
    Jobs removed from yaml are ``enabled=0`` (not deleted) so future run history
    can keep foreign keys.
    """
    from bunsui.config import load_config

    cfg = config if config is not None else load_config(paths)
    decls = parse_jobs(cfg)
    bootstrap_sqlite(paths.sqlite_path)

    now = utc_now_iso()
    created = updated = disabled = 0
    declared_names = {d.name for d in decls}

    with connect(paths.sqlite_path) as conn:
        existing_rows = {
            row["name"]: row
            for row in conn.execute(
                "SELECT id, name, job_type, config_json, depends_on_json, "
                "execution_mode, enabled FROM jobs"
            ).fetchall()
        }

        for decl in decls:
            config_json = json.dumps(decl.config, sort_keys=True)
            depends_json = json.dumps(decl.depends_on, ensure_ascii=False)
            prev = existing_rows.get(decl.name)
            if prev is None:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, name, job_type, config_json, depends_on_json,
                        execution_mode, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        decl.name,
                        decl.job_type,
                        config_json,
                        depends_json,
                        decl.execution_mode,
                        now,
                        now,
                    ),
                )
                created += 1
            else:
                same = (
                    prev["job_type"] == decl.job_type
                    and (prev["config_json"] or "null") == config_json
                    and (prev["depends_on_json"] or "null") == depends_json
                    and prev["execution_mode"] == decl.execution_mode
                    and int(prev["enabled"]) == 1
                )
                if not same:
                    conn.execute(
                        """
                        UPDATE jobs SET
                            job_type = ?,
                            config_json = ?,
                            depends_on_json = ?,
                            execution_mode = ?,
                            enabled = 1,
                            updated_at = ?
                        WHERE name = ?
                        """,
                        (
                            decl.job_type,
                            config_json,
                            depends_json,
                            decl.execution_mode,
                            now,
                            decl.name,
                        ),
                    )
                    updated += 1

        for name, row in existing_rows.items():
            if name not in declared_names and int(row["enabled"]) == 1:
                conn.execute(
                    "UPDATE jobs SET enabled = 0, updated_at = ? WHERE name = ?",
                    (now, name),
                )
                disabled += 1

        conn.commit()

    return SyncResult(created=created, updated=updated, disabled=disabled)
