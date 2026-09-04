import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { Database } from "bun:sqlite";
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { createApp } from "../src/app";

const tmpRoot = join(import.meta.dir, ".tmp-test");
const sqlitePath = join(tmpRoot, "control.sqlite");

const SCHEMA = `
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE assets (
  id TEXT PRIMARY KEY, asset_key TEXT NOT NULL UNIQUE, asset_type TEXT,
  status TEXT NOT NULL DEFAULT 'unknown', parent_asset_id TEXT,
  last_materialized_at TEXT, last_run_id TEXT, metadata_json TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE jobs (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, job_type TEXT NOT NULL,
  config_json TEXT, depends_on_json TEXT, execution_mode TEXT NOT NULL DEFAULT 'sync',
  enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE job_runs (
  id TEXT PRIMARY KEY, job_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
  trigger TEXT, started_at TEXT, finished_at TEXT, error_message TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE asset_materializations (
  id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, job_run_id TEXT, status TEXT NOT NULL,
  materialized_at TEXT, metadata_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE logs (
  id TEXT PRIMARY KEY, job_run_id TEXT NOT NULL, log_kind TEXT NOT NULL DEFAULT 'stdout',
  path TEXT, blob_pointer TEXT, created_at TEXT NOT NULL
);
CREATE TABLE artifacts (
  id TEXT PRIMARY KEY, job_run_id TEXT NOT NULL, artifact_type TEXT NOT NULL,
  path TEXT NOT NULL, retained_until TEXT, created_at TEXT NOT NULL
);
`;

beforeAll(() => {
  rmSync(tmpRoot, { recursive: true, force: true });
  mkdirSync(tmpRoot, { recursive: true });
  const db = new Database(sqlitePath);
  db.exec(SCHEMA);
  db.run(
    `INSERT INTO schema_migrations (version, applied_at) VALUES (1, '2026-01-01T00:00:00+00:00')`,
  );
  db.close();
});

afterAll(() => {
  rmSync(tmpRoot, { recursive: true, force: true });
});

describe("health / status", () => {
  test("GET /health returns ok", async () => {
    const app = createApp({ sqlitePath });
    const res = await app.request("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.service).toBe("bunsui-api");
    expect(body.sqlite).toBe("connected");
  });

  test("GET /api/status returns empty counts", async () => {
    const app = createApp({ sqlitePath });
    const res = await app.request("/api/status");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.counts.jobs).toBe(0);
    expect(body.counts.assets).toBe(0);
  });

  test("GET /api/jobs includes last run fields when present", async () => {
    const db = new Database(sqlitePath);
    db.run(
      `INSERT INTO jobs (id, name, job_type, execution_mode, enabled, created_at, updated_at)
       VALUES ('j1', 'demo', 'python', 'sync', 1, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`,
    );
    db.run(
      `INSERT INTO job_runs (id, job_id, status, started_at, finished_at, created_at, updated_at)
       VALUES ('r1', 'j1', 'succeeded', '2026-01-01T01:00:00+00:00', '2026-01-01T01:00:01+00:00',
               '2026-01-01T01:00:00+00:00', '2026-01-01T01:00:01+00:00')`,
    );
    db.close();

    const app = createApp({ sqlitePath });
    const res = await app.request("/api/jobs");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobs).toHaveLength(1);
    expect(body.jobs[0].name).toBe("demo");
    expect(body.jobs[0].last_run_status).toBe("succeeded");
    expect(body.jobs[0].last_finished_at).toBe("2026-01-01T01:00:01+00:00");
  });

  test("GET /api/logs/:id returns captured log content", async () => {
    const { writeFileSync } = await import("node:fs");
    const logFile = join(tmpRoot, "run.log");
    writeFileSync(logFile, "hello from dbt\n", "utf8");

    const db = new Database(sqlitePath);
    db.run(
      `INSERT INTO jobs (id, name, job_type, execution_mode, enabled, created_at, updated_at)
       VALUES ('j2', 'dbt_demo', 'dbt', 'sync', 1, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`,
    );
    db.run(
      `INSERT INTO job_runs (id, job_id, status, started_at, finished_at, created_at, updated_at)
       VALUES ('r2', 'j2', 'succeeded', '2026-01-01T02:00:00+00:00', '2026-01-01T02:00:01+00:00',
               '2026-01-01T02:00:00+00:00', '2026-01-01T02:00:01+00:00')`,
    );
    db.run(
      `INSERT INTO logs (id, job_run_id, log_kind, path, created_at)
       VALUES ('l1', 'r2', 'combined', ?, '2026-01-01T02:00:01+00:00')`,
      [logFile],
    );
    db.close();

    const app = createApp({ sqlitePath, projectRoot: tmpRoot });
    const res = await app.request("/api/logs/l1");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe("l1");
    expect(body.job_run_id).toBe("r2");
    expect(body.content).toContain("hello from dbt");
  });
});
