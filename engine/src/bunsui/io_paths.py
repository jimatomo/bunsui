"""Thin local path / glob helpers for file IO jobs.

Today this only resolves paths under a project root. A future revision can
accept ``s3://`` / other URIs (or delegate to ``ArtifactStore``) without
changing call sites that already go through ``resolve_data_path``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedDataPath:
    """A path (or DuckDB-compatible glob) resolved against the project root."""

    # Absolute path or absolute glob pattern passed to DuckDB read_* helpers.
    duckdb_path: str
    # Project-relative form for logs / metadata (uses forward slashes).
    display_path: str
    # Concrete matched files (empty when the pattern matches nothing).
    matched_files: tuple[Path, ...]


def resolve_data_path(project_root: Path, path_spec: str) -> ResolvedDataPath:
    """Resolve a relative file or glob under ``project_root``.

    Absolute paths and ``..`` escapes outside the project are rejected so loads
    stay local-first and reviewable. Globs use ``Path.glob`` semantics.
    """
    if not isinstance(path_spec, str) or not path_spec.strip():
        raise ValueError("path must be a non-empty string")
    raw = path_spec.strip().replace("\\", "/")
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        raise ValueError(f"path must be relative to the project root, got {path_spec!r}")
    if raw.startswith("~"):
        raise ValueError(f"path must be relative to the project root, got {path_spec!r}")

    root = project_root.resolve()
    # Glob characters → match under root; otherwise treat as a single file.
    if any(ch in raw for ch in "*?["):
        matches = sorted(p for p in root.glob(raw) if p.is_file())
        # Guard against glob escaping via odd patterns (resolved paths).
        safe = []
        for match in matches:
            resolved = match.resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"path {path_spec!r} resolves outside the project root"
                ) from exc
            safe.append(resolved)
        duckdb_path = str(root / raw)
        return ResolvedDataPath(
            duckdb_path=duckdb_path,
            display_path=raw,
            matched_files=tuple(safe),
        )

    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"path {path_spec!r} resolves outside the project root"
        ) from exc
    matched = (candidate,) if candidate.is_file() else ()
    return ResolvedDataPath(
        duckdb_path=str(candidate),
        display_path=raw,
        matched_files=matched,
    )
