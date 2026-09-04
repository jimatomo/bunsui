"""Ingest dbt ``run_results.json`` into ``assets`` / ``asset_materializations``.

After a dbt job run, copy ``target/run_results.json`` under ``artifacts/`` (when
present), then upsert asset rows. Tests become children of their model when the
relation is clear from ``manifest.json`` (``attached_node`` / ``depends_on``) or,
as a fallback, when the same results list contains a single model.

A test failure marks the **parent model** asset status as ``failed``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bunsui.paths import ARTIFACTS_DIRNAME, ProjectPaths

# dbt result status → assets.status
_ASSET_STATUS = {
    "success": "materialized",
    "pass": "materialized",
    "warn": "materialized",
    "error": "failed",
    "fail": "failed",
    "runtime error": "failed",
    "skipped": "skipped",
}

# dbt result status → asset_materializations.status
_MAT_STATUS = {
    "success": "succeeded",
    "pass": "succeeded",
    "warn": "succeeded",
    "error": "failed",
    "fail": "failed",
    "runtime error": "failed",
    "skipped": "skipped",
}

_KNOWN_RESOURCE_TYPES = frozenset(
    {"model", "test", "seed", "snapshot", "source", "analysis", "operation", "unit_test"}
)


def resource_type_from_unique_id(unique_id: str) -> str:
    """Map ``model.proj.name`` → ``model`` (unknown prefixes → ``other``)."""
    prefix, _, _ = unique_id.partition(".")
    if prefix in _KNOWN_RESOURCE_TYPES:
        return prefix
    return "other"


def map_asset_status(dbt_status: str) -> str:
    return _ASSET_STATUS.get(dbt_status.lower().strip(), "unknown")


def map_materialization_status(dbt_status: str) -> str:
    return _MAT_STATUS.get(dbt_status.lower().strip(), "failed")


def find_run_results_path(dbt_dir: Path) -> Path | None:
    path = dbt_dir / "target" / "run_results.json"
    return path if path.is_file() else None


def load_parent_map(
    *,
    results: list[dict[str, Any]],
    manifest_path: Path | None,
) -> dict[str, str]:
    """Return ``test_unique_id → parent_model_unique_id`` when relation is clear."""
    parents: dict[str, str] = {}

    if manifest_path is not None and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        nodes = manifest.get("nodes") if isinstance(manifest, dict) else None
        if isinstance(nodes, dict):
            for uid, node in nodes.items():
                if not isinstance(node, dict):
                    continue
                if resource_type_from_unique_id(str(uid)) != "test":
                    continue
                attached = node.get("attached_node")
                if isinstance(attached, str) and attached.startswith("model."):
                    parents[str(uid)] = attached
                    continue
                depends = node.get("depends_on") or {}
                dep_nodes = depends.get("nodes") if isinstance(depends, dict) else None
                if isinstance(dep_nodes, list):
                    models = [n for n in dep_nodes if isinstance(n, str) and n.startswith("model.")]
                    if len(models) == 1:
                        parents[str(uid)] = models[0]

    # Fallback: single model in this run_results → attach orphan tests to it.
    model_uids = [
        str(r["unique_id"])
        for r in results
        if isinstance(r, dict)
        and isinstance(r.get("unique_id"), str)
        and resource_type_from_unique_id(str(r["unique_id"])) == "model"
    ]
    if len(model_uids) == 1:
        only_model = model_uids[0]
        for r in results:
            if not isinstance(r, dict):
                continue
            uid = r.get("unique_id")
            if not isinstance(uid, str):
                continue
            if resource_type_from_unique_id(uid) == "test" and uid not in parents:
                parents[uid] = only_model

    return parents


def parse_run_results(
    payload: dict[str, Any],
    *,
    parent_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Normalize ``run_results.json`` results into ingest rows (models before tests)."""
    raw = payload.get("results")
    if not isinstance(raw, list):
        return []

    parents = parent_map or {}
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        unique_id = item.get("unique_id")
        if not isinstance(unique_id, str) or not unique_id:
            continue
        dbt_status = str(item.get("status") or "unknown")
        asset_type = resource_type_from_unique_id(unique_id)
        rows.append(
            {
                "asset_key": unique_id,
                "asset_type": asset_type,
                "dbt_status": dbt_status,
                "asset_status": map_asset_status(dbt_status),
                "mat_status": map_materialization_status(dbt_status),
                "parent_key": parents.get(unique_id),
                "message": item.get("message"),
                "failures": item.get("failures"),
                "relation_name": item.get("relation_name"),
            }
        )

    # Parents (non-tests) first so child upserts can resolve parent_asset_id.
    rows.sort(key=lambda r: (0 if r["asset_type"] != "test" else 1, r["asset_key"]))
    return rows


def _retained_until_iso(now: datetime, retention_days: int) -> str:
    return (now + timedelta(days=retention_days)).astimezone(timezone.utc).isoformat()


def retain_run_results_artifact(
    conn: Any,
    *,
    paths: ProjectPaths,
    run_id: str,
    source: Path,
    created_at: str,
    retention_days: int,
) -> str:
    """Copy ``run_results.json`` into ``artifacts/`` and insert an ``artifacts`` row.

    Returns the relative path stored in SQLite.
    """
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    rel = f"{ARTIFACTS_DIRNAME}/{run_id}-run_results.json"
    dest = paths.root / rel
    dest.write_bytes(source.read_bytes())

    retained_until: str | None = None
    if retention_days > 0:
        try:
            created = datetime.fromisoformat(created_at)
        except ValueError:
            created = datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        retained_until = _retained_until_iso(created, retention_days)

    conn.execute(
        """
        INSERT INTO artifacts (
            id, job_run_id, artifact_type, path, retained_until, created_at
        ) VALUES (?, ?, 'run_results_json', ?, ?, ?)
        """,
        (str(uuid.uuid4()), run_id, rel, retained_until, created_at),
    )
    return rel


def upsert_assets_from_rows(
    conn: Any,
    *,
    rows: list[dict[str, Any]],
    run_id: str,
    materialized_at: str,
) -> list[str]:
    """Upsert ``assets`` + ``asset_materializations``. Returns upserted asset_keys.

    Test failures also set the parent model asset status to ``failed``.
    """
    if not rows:
        return []

    existing = {
        str(r["asset_key"]): dict(r)
        for r in conn.execute(
            "SELECT id, asset_key, parent_asset_id FROM assets"
        ).fetchall()
    }
    key_to_id = {k: str(v["id"]) for k, v in existing.items()}
    upserted: list[str] = []
    failed_parent_keys: set[str] = set()

    for row in rows:
        asset_key = row["asset_key"]
        parent_key = row.get("parent_key")
        parent_id = key_to_id.get(parent_key) if parent_key else None

        meta = {
            "dbt_status": row["dbt_status"],
            "message": row.get("message"),
            "failures": row.get("failures"),
            "relation_name": row.get("relation_name"),
        }
        metadata_json = json.dumps(meta, ensure_ascii=False)

        if asset_key in key_to_id:
            asset_id = key_to_id[asset_key]
            conn.execute(
                """
                UPDATE assets SET
                    asset_type = ?,
                    status = ?,
                    parent_asset_id = COALESCE(?, parent_asset_id),
                    last_materialized_at = ?,
                    last_run_id = ?,
                    metadata_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    row["asset_type"],
                    row["asset_status"],
                    parent_id,
                    materialized_at,
                    run_id,
                    metadata_json,
                    materialized_at,
                    asset_id,
                ),
            )
        else:
            asset_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO assets (
                    id, asset_key, asset_type, status, parent_asset_id,
                    last_materialized_at, last_run_id, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    asset_key,
                    row["asset_type"],
                    row["asset_status"],
                    parent_id,
                    materialized_at,
                    run_id,
                    metadata_json,
                    materialized_at,
                    materialized_at,
                ),
            )
            key_to_id[asset_key] = asset_id

        conn.execute(
            """
            INSERT INTO asset_materializations (
                id, asset_id, job_run_id, status, materialized_at,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                asset_id,
                run_id,
                row["mat_status"],
                materialized_at,
                metadata_json,
                materialized_at,
            ),
        )
        upserted.append(asset_key)

        if row["asset_type"] == "test" and row["asset_status"] == "failed" and parent_key:
            failed_parent_keys.add(parent_key)

    for parent_key in failed_parent_keys:
        parent_id = key_to_id.get(parent_key)
        if parent_id is None:
            continue
        conn.execute(
            """
            UPDATE assets SET
                status = 'failed',
                last_run_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (run_id, materialized_at, parent_id),
        )

    return upserted


def ingest_dbt_run_results(
    conn: Any,
    *,
    paths: ProjectPaths,
    run_id: str,
    created_at: str,
    retention_days: int = 30,
    run_results_path: Path | None = None,
) -> list[str]:
    """Retain + parse ``run_results.json`` and upsert assets. No-op if file missing."""
    source = run_results_path or find_run_results_path(paths.dbt_dir)
    if source is None or not source.is_file():
        return []

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    retain_run_results_artifact(
        conn,
        paths=paths,
        run_id=run_id,
        source=source,
        created_at=created_at,
        retention_days=retention_days,
    )

    results = payload.get("results")
    if not isinstance(results, list):
        results = []
    parent_map = load_parent_map(
        results=results,
        manifest_path=source.parent / "manifest.json",
    )
    rows = parse_run_results(payload, parent_map=parent_map)
    return upsert_assets_from_rows(
        conn,
        rows=rows,
        run_id=run_id,
        materialized_at=created_at,
    )
