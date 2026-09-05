"""Unit tests for dbt ``run_results.json`` → assets ingest (offline fixtures)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bunsui.db import connect
from bunsui.project import init_project
from bunsui.run_results import (
    ingest_dbt_run_results,
    load_parent_map,
    map_asset_status,
    parse_run_results,
    resource_type_from_unique_id,
    upsert_assets_from_rows,
)
from bunsui.runner import run_job

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_resource_type_and_status_maps() -> None:
    assert resource_type_from_unique_id("model.proj.orders") == "model"
    assert resource_type_from_unique_id("test.proj.not_null_orders_id.abc") == "test"
    assert resource_type_from_unique_id("seed.proj.raw") == "seed"
    assert resource_type_from_unique_id("weird.proj.x") == "other"
    assert map_asset_status("success") == "materialized"
    assert map_asset_status("pass") == "materialized"
    assert map_asset_status("fail") == "failed"
    assert map_asset_status("error") == "failed"
    assert map_asset_status("skipped") == "skipped"


def test_parse_success_fixture_with_manifest_parent() -> None:
    payload = _load("run_results_success.json")
    parents = load_parent_map(
        results=payload["results"],
        manifest_path=FIXTURES / "manifest_success.json",
    )
    rows = parse_run_results(payload, parent_map=parents)
    assert [r["asset_key"] for r in rows][0].startswith("model.")
    model = next(r for r in rows if r["asset_type"] == "model")
    test = next(r for r in rows if r["asset_type"] == "test")
    assert model["asset_status"] == "materialized"
    assert test["asset_status"] == "materialized"
    assert test["parent_key"] == model["asset_key"]


def test_parse_test_failure_marks_parent_failed(tmp_path: Path) -> None:
    root = tmp_path / "fail_assets"
    root.mkdir()
    paths = init_project(root, name="fail_assets")
    payload = _load("run_results_test_fail.json")
    parents = load_parent_map(
        results=payload["results"],
        manifest_path=FIXTURES / "manifest_test_fail.json",
    )
    rows = parse_run_results(payload, parent_map=parents)
    with connect(paths.sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, name, job_type, config_json, depends_on_json,
                execution_mode, enabled, created_at, updated_at
            ) VALUES ('job1', 'j', 'dbt', '{}', '[]', 'sync', 1, 't', 't')
            """
        )
        conn.execute(
            """
            INSERT INTO job_runs (
                id, job_id, status, trigger, started_at, finished_at,
                error_message, created_at, updated_at
            ) VALUES ('run-fail-1', 'job1', 'failed', 'manual', 't', 't', NULL, 't', 't')
            """
        )
        upsert_assets_from_rows(
            conn,
            rows=rows,
            run_id="run-fail-1",
            materialized_at="2026-01-01T00:00:00+00:00",
        )
        conn.commit()
        assets = {
            r["asset_key"]: r
            for r in conn.execute(
                "SELECT id, asset_key, asset_type, status, parent_asset_id FROM assets"
            ).fetchall()
        }
        model_key = next(k for k in assets if k.startswith("model."))
        test_key = next(k for k in assets if k.startswith("test."))
        assert assets[test_key]["status"] == "failed"
        assert assets[model_key]["status"] == "failed"
        assert assets[test_key]["parent_asset_id"] == assets[model_key]["id"]
        mats = conn.execute(
            "SELECT COUNT(*) AS c FROM asset_materializations"
        ).fetchone()["c"]
        assert mats == 2


def test_single_model_fallback_without_manifest() -> None:
    payload = _load("run_results_success.json")
    parents = load_parent_map(results=payload["results"], manifest_path=None)
    assert len(parents) == 1
    test_uid = next(r["unique_id"] for r in payload["results"] if r["unique_id"].startswith("test."))
    model_uid = next(r["unique_id"] for r in payload["results"] if r["unique_id"].startswith("model."))
    assert parents[test_uid] == model_uid


def test_ingest_copies_artifact_and_upserts(tmp_path: Path) -> None:
    root = tmp_path / "ingest"
    root.mkdir()
    paths = init_project(root, name="ingest")
    target = paths.dbt_dir / "target"
    target.mkdir(parents=True)
    shutil.copy(FIXTURES / "run_results_success.json", target / "run_results.json")
    shutil.copy(FIXTURES / "manifest_success.json", target / "manifest.json")

    with connect(paths.sqlite_path) as conn:
        # Need a job_runs row for FK on artifacts / materializations
        conn.execute(
            """
            INSERT INTO jobs (
                id, name, job_type, config_json, depends_on_json,
                execution_mode, enabled, created_at, updated_at
            ) VALUES ('job1', 'j', 'dbt', '{}', '[]', 'sync', 1, 't', 't')
            """
        )
        conn.execute(
            """
            INSERT INTO job_runs (
                id, job_id, status, trigger, started_at, finished_at,
                error_message, created_at, updated_at
            ) VALUES ('run1', 'job1', 'succeeded', 'manual', 't', 't', NULL, 't', 't')
            """
        )
        keys = ingest_dbt_run_results(
            conn,
            paths=paths,
            run_id="run1",
            created_at="2026-01-02T00:00:00+00:00",
            retention_days=7,
        )
        conn.commit()
        assert any(k.startswith("model.") for k in keys)
        art = conn.execute(
            "SELECT artifact_type, path, retained_until FROM artifacts WHERE job_run_id = ?",
            ("run1",),
        ).fetchone()
        assert art["artifact_type"] == "run_results_json"
        assert art["path"] == "artifacts/run1-run_results.json"
        assert art["retained_until"]
        assert (paths.root / art["path"]).is_file()
        assert conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"] >= 2


def test_run_dbt_real_duckdb_populates_assets(tmp_path: Path) -> None:
    if shutil.which("dbt") is None:
        pytest.skip("dbt CLI not on PATH")

    root = tmp_path / "demo_assets"
    root.mkdir()
    paths = init_project(root, name="demo_assets")
    result = run_job(paths, "example_dbt")
    assert result.status == "succeeded", result.error_message

    with connect(paths.sqlite_path) as conn:
        assets = list(
            conn.execute(
                "SELECT id, asset_key, asset_type, status, parent_asset_id FROM assets "
                "ORDER BY asset_key"
            )
        )
        assert len(assets) >= 1
        models = [a for a in assets if a["asset_type"] == "model"]
        assert len(models) >= 1
        assert models[0]["status"] == "materialized"
        assert "example" in models[0]["asset_key"]
        tests = [a for a in assets if a["asset_type"] == "test"]
        assert len(tests) >= 1
        assert tests[0]["parent_asset_id"] == models[0]["id"]
        assert tests[0]["status"] == "materialized"
        art = conn.execute(
            "SELECT path FROM artifacts WHERE job_run_id = ?", (result.run_id,)
        ).fetchone()
        assert art is not None
        assert (paths.root / art["path"]).is_file()


def test_retain_uses_injected_artifact_store(tmp_path: Path) -> None:
    """retain/ingest accept an injected ArtifactStore (DI seam for cloud later)."""
    from bunsui.artifacts import LocalArtifactStore

    root = tmp_path / "store"
    root.mkdir()
    paths = init_project(root, name="store")
    source = tmp_path / "incoming.json"
    source.write_text('{"metadata": {}, "results": []}', encoding="utf-8")

    # Root the store somewhere other than the default artifacts/ to prove injection.
    alt_root = tmp_path / "alt_blobs"
    store = LocalArtifactStore(alt_root)

    with connect(paths.sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, name, job_type, config_json, depends_on_json,
                execution_mode, enabled, created_at, updated_at
            ) VALUES ('job1', 'j', 'dbt', '{}', '[]', 'sync', 1, 't', 't')
            """
        )
        conn.execute(
            """
            INSERT INTO job_runs (
                id, job_id, status, trigger, started_at, finished_at,
                error_message, created_at, updated_at
            ) VALUES ('run1', 'job1', 'succeeded', 'manual', 't', 't', NULL, 't', 't')
            """
        )
        from bunsui.run_results import retain_run_results_artifact

        rel = retain_run_results_artifact(
            conn,
            paths=paths,
            run_id="run1",
            source=source,
            created_at="2026-01-01T00:00:00+00:00",
            retention_days=7,
            store=store,
        )
        conn.commit()
        assert rel == "artifacts/run1-run_results.json"
        # Bytes landed in the injected store root, not necessarily paths.artifacts_dir
        assert (alt_root / "run1-run_results.json").is_file()
        art = conn.execute(
            "SELECT path FROM artifacts WHERE job_run_id = ?",
            ("run1",),
        ).fetchone()
        assert art["path"] == "artifacts/run1-run_results.json"


def test_local_artifact_store_roundtrip(tmp_path: Path) -> None:
    from bunsui.artifacts import LocalArtifactStore

    store = LocalArtifactStore(tmp_path / "blobs")
    key = store.put("a/b.json", b'{"ok":true}', content_type="application/json")
    assert key == "a/b.json"
    assert store.exists(key)
    assert store.get(key) == b'{"ok":true}'
