"""Blob artifact storage seam (local-first; cloud backends can plug in later).

``LocalArtifactStore`` keeps bytes under the project's ``artifacts/`` directory.
Logical keys are relative to that directory (for example
``{run_id}-run_results.json``). SQLite ``artifacts.path`` stores the
project-relative form ``artifacts/{key}`` so callers never need absolute paths.

A future S3/GCS implementation can satisfy the same ``ArtifactStore`` protocol
without rewriting dbt ingest or retry restore logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from bunsui.paths import ARTIFACTS_DIRNAME, ProjectPaths


@runtime_checkable
class ArtifactStore(Protocol):
    """Put/get opaque blobs by logical key."""

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        """Store ``data`` under ``key``. Returns the logical key."""

    def get(self, key: str) -> bytes:
        """Return bytes for ``key`` or raise ``FileNotFoundError``."""

    def exists(self, key: str) -> bool:
        """Return True when ``key`` is present."""


class LocalArtifactStore:
    """Filesystem ``ArtifactStore`` rooted at ``artifacts_dir``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        del content_type  # reserved for cloud backends (S3 Content-Type, etc.)
        if not key or key.startswith("/") or ".." in Path(key).parts:
            raise ValueError(f"invalid artifact key: {key!r}")
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        path = self.root / key
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return (self.root / key).is_file()


def local_artifact_store(paths: ProjectPaths) -> LocalArtifactStore:
    """Default store: project ``artifacts/`` directory."""
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return LocalArtifactStore(paths.artifacts_dir)


def project_relative_artifact_path(key: str) -> str:
    """SQLite ``artifacts.path`` value for a store key (under project root)."""
    return f"{ARTIFACTS_DIRNAME}/{key}"


def run_results_artifact_key(run_id: str) -> str:
    """Final retained ``run_results.json`` key for a job run."""
    return f"{run_id}-run_results.json"


def retry_run_results_key(run_id: str, attempt: int) -> str:
    """Per-attempt key used to feed native ``dbt retry``."""
    return f"{run_id}/attempt-{attempt}-run_results.json"


def retry_run_results_latest_key(run_id: str) -> str:
    """Overwrite-friendly key for the latest failed attempt's run_results."""
    return f"{run_id}/latest-run_results.json"
