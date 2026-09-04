"""Declare jobs in ``bunsui.yaml`` and/or ``jobs/*.yaml``, sync into SQLite.

This module syncs declarations into the ``jobs`` table. Execution of python
callables and dbt CLI jobs lives in ``bunsui.runner`` (``bunsui job run``).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from bunsui.db import bootstrap_sqlite, connect, utc_now_iso
from bunsui.paths import JOBS_DIRNAME, ProjectPaths

ALLOWED_JOB_TYPES = frozenset({"dbt", "python"})
ALLOWED_EXECUTION_MODES = frozenset({"sync", "async"})

INLINE_SOURCE = "bunsui.yaml"


@dataclass(frozen=True)
class JobDecl:
    """One job declaration from yaml (inline or ``jobs/`` file)."""

    name: str
    job_type: str
    execution_mode: str
    depends_on: list[str]
    config: dict[str, Any]
    source: str = INLINE_SOURCE


@dataclass(frozen=True)
class SyncResult:
    """Counts from a single ``job sync`` pass."""

    created: int
    updated: int
    disabled: int

    @property
    def upserted(self) -> int:
        return self.created + self.updated


def jobs_dir(paths: ProjectPaths, config: dict[str, Any] | None = None) -> Path:
    """Directory of split job yaml files (default ``jobs/``; override via ``paths.jobs``)."""
    cfg = config or {}
    path_cfg = cfg.get("paths") if isinstance(cfg.get("paths"), dict) else {}
    rel = path_cfg.get("jobs", JOBS_DIRNAME) if isinstance(path_cfg, dict) else JOBS_DIRNAME
    if not isinstance(rel, str) or not rel.strip():
        rel = JOBS_DIRNAME
    candidate = Path(rel)
    return candidate if candidate.is_absolute() else (paths.root / candidate)


def _default_execution_mode(config: dict[str, Any] | None) -> str:
    if not config:
        return "sync"
    defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
    mode = defaults.get("job_execution_mode", "sync") if isinstance(defaults, dict) else "sync"
    return str(mode) if mode else "sync"


def _parse_job_mapping(
    item: dict[str, Any],
    *,
    source: str,
    index: int | None,
    default_mode: str,
) -> JobDecl:
    loc = f"{source}" if index is None else f"{source} jobs[{index}]"
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{loc}: requires a non-empty name")
    name = name.strip()

    job_type = item.get("type")
    if job_type not in ALLOWED_JOB_TYPES:
        raise ValueError(
            f"{source}: job {name!r} type must be one of "
            f"{sorted(ALLOWED_JOB_TYPES)}, got {job_type!r}"
        )

    mode = item.get("execution_mode", default_mode)
    if mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError(
            f"{source}: job {name!r} execution_mode must be one of "
            f"{sorted(ALLOWED_EXECUTION_MODES)}, got {mode!r}"
        )

    depends_on = item.get("depends_on") or []
    if not isinstance(depends_on, list) or not all(
        isinstance(d, str) and d.strip() for d in depends_on
    ):
        raise ValueError(f"{source}: job {name!r} depends_on must be a list of names")
    depends_on = [d.strip() for d in depends_on]

    config_obj = item.get("config") or {}
    if not isinstance(config_obj, dict):
        raise ValueError(f"{source}: job {name!r} config must be a mapping")

    return JobDecl(
        name=name,
        job_type=str(job_type),
        execution_mode=str(mode),
        depends_on=depends_on,
        config=dict(config_obj),
        source=source,
    )


def _mappings_from_document(data: Any, source: str) -> list[tuple[dict[str, Any], int | None]]:
    """Normalize a loaded yaml document into (mapping, optional list index) pairs."""
    if data is None:
        return []
    if isinstance(data, list):
        out: list[tuple[dict[str, Any], int | None]] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"{source}: list item [{i}] must be a job mapping")
            out.append((item, i))
        return out
    if isinstance(data, dict):
        if "jobs" in data:
            raw = data.get("jobs")
            if raw is None:
                return []
            if not isinstance(raw, list):
                raise ValueError(f"{source}: jobs must be a list")
            out = []
            for i, item in enumerate(raw):
                if not isinstance(item, dict):
                    raise ValueError(f"{source}: jobs[{i}] must be a mapping")
                out.append((item, i))
            return out
        # Single job mapping (name + type required; validated later).
        return [(data, None)]
    raise ValueError(f"{source}: expected a job mapping, jobs: list, or YAML list")


def _iter_job_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        # Skip any path segment that starts with '.' (e.g. jobs/.hidden/x.yaml).
        try:
            rel = path.relative_to(directory)
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(path)
    return files


def load_declared_jobs(
    paths: ProjectPaths,
    config: dict[str, Any] | None = None,
) -> list[JobDecl]:
    """Load and merge inline ``jobs:`` plus ``jobs/**/*.yaml`` declarations."""
    from bunsui.config import load_config

    cfg = config if config is not None else load_config(paths)
    default_mode = _default_execution_mode(cfg)
    by_name: dict[str, JobDecl] = {}

    def _add(decl: JobDecl) -> None:
        prev = by_name.get(decl.name)
        if prev is not None:
            raise ValueError(
                f"duplicate job name {decl.name!r} in {prev.source} and {decl.source}"
            )
        by_name[decl.name] = decl

    # Inline jobs in bunsui.yaml (optional).
    if "jobs" in cfg and cfg.get("jobs") is not None:
        if not isinstance(cfg.get("jobs"), list):
            raise ValueError(f"{INLINE_SOURCE}: jobs must be a list")
        for mapping, index in _mappings_from_document({"jobs": cfg["jobs"]}, INLINE_SOURCE):
            _add(
                _parse_job_mapping(
                    mapping, source=INLINE_SOURCE, index=index, default_mode=default_mode
                )
            )

    jobs_root = jobs_dir(paths, cfg)
    for file_path in _iter_job_files(jobs_root):
        rel = file_path.relative_to(paths.root)
        source = str(rel).replace("\\", "/")
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        for mapping, index in _mappings_from_document(data, source):
            _add(
                _parse_job_mapping(
                    mapping, source=source, index=index, default_mode=default_mode
                )
            )

    jobs = list(by_name.values())
    known = {j.name for j in jobs}
    for job in jobs:
        for dep in job.depends_on:
            if dep == job.name:
                raise ValueError(
                    f"{job.source}: job {job.name!r} cannot depend on itself"
                )
            if dep not in known:
                raise ValueError(
                    f"{job.source}: job {job.name!r} depends_on unknown job {dep!r}"
                )
    return jobs


def parse_jobs(config: dict[str, Any]) -> list[JobDecl]:
    """Parse inline ``jobs:`` only (no filesystem). Prefer ``load_declared_jobs``."""
    default_mode = _default_execution_mode(config)
    raw = config.get("jobs", [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{INLINE_SOURCE}: jobs must be a list")
    by_name: dict[str, JobDecl] = {}
    for mapping, index in _mappings_from_document({"jobs": raw}, INLINE_SOURCE):
        decl = _parse_job_mapping(
            mapping, source=INLINE_SOURCE, index=index, default_mode=default_mode
        )
        if decl.name in by_name:
            raise ValueError(
                f"duplicate job name {decl.name!r} in {INLINE_SOURCE} and {INLINE_SOURCE}"
            )
        by_name[decl.name] = decl
    jobs = list(by_name.values())
    known = {j.name for j in jobs}
    for job in jobs:
        for dep in job.depends_on:
            if dep == job.name:
                raise ValueError(
                    f"{INLINE_SOURCE}: job {job.name!r} cannot depend on itself"
                )
            if dep not in known:
                raise ValueError(
                    f"{INLINE_SOURCE}: job {job.name!r} depends_on unknown job {dep!r}"
                )
    return jobs


def example_job_files() -> dict[str, dict[str, Any]]:
    """Filename → single-job mapping written by ``bunsui init`` under ``jobs/``."""
    return {
        "example_dbt.yaml": {
            "name": "example_dbt",
            "type": "dbt",
            "execution_mode": "sync",
            "depends_on": [],
            "config": {
                "command": "run",
                "select": "example",
            },
        },
        "example_python.yaml": {
            "name": "example_python",
            "type": "python",
            "execution_mode": "sync",
            "depends_on": ["example_dbt"],
            "config": {
                "callable": "sample:main",
            },
        },
        "example_python_async.yaml": {
            "name": "example_python_async",
            "type": "python",
            "execution_mode": "async",
            "depends_on": [],
            "config": {
                "callable": "sample:async_main",
            },
        },
    }


def write_example_job_files(directory: Path) -> None:
    """Write sample split job yaml files into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    for filename, body in example_job_files().items():
        path = directory / filename
        header = "# bunsui job declaration (synced with `bunsui job sync`)\n"
        path.write_text(header + yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def sync_jobs(paths: ProjectPaths, config: dict[str, Any] | None = None) -> SyncResult:
    """Upsert yaml jobs into SQLite; disable rows no longer listed.

    Idempotent: re-running with the same declarations yields the same enabled rows.
    Jobs removed from yaml/files are ``enabled=0`` (not deleted) so future run
    history can keep foreign keys.
    """
    from bunsui.config import load_config

    cfg = config if config is not None else load_config(paths)
    decls = load_declared_jobs(paths, cfg)
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
