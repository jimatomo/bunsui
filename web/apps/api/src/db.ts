/**
 * Thin SQLite reader for the control plane.
 * Engine (Python) owns schema migrations and writes.
 */

import { Database } from "bun:sqlite";

export type JobRow = {
  id: string;
  name: string;
  job_type: string;
  execution_mode: string;
  enabled: number;
  status?: string | null;
};

export type AssetRow = {
  id: string;
  asset_key: string;
  asset_type: string | null;
  status: string;
  parent_asset_id: string | null;
  last_materialized_at: string | null;
};

export type JobRunRow = {
  id: string;
  job_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
};

export type LogRow = {
  id: string;
  job_run_id: string;
  log_kind: string;
  path: string | null;
};

export class ControlDb {
  readonly path: string;
  private db: Database;

  constructor(path: string) {
    this.path = path;
    this.db = new Database(path, { readonly: true, create: false });
  }

  counts(): Record<string, number> {
    const tables = [
      "assets",
      "jobs",
      "job_runs",
      "asset_materializations",
      "logs",
      "artifacts",
    ] as const;
    const out: Record<string, number> = {};
    for (const t of tables) {
      try {
        const row = this.db.query(`SELECT COUNT(*) AS c FROM ${t}`).get() as {
          c: number;
        };
        out[t] = row.c;
      } catch {
        out[t] = -1;
      }
    }
    return out;
  }

  listJobs(): JobRow[] {
    return this.db
      .query(
        `SELECT id, name, job_type, execution_mode, enabled FROM jobs ORDER BY name`,
      )
      .all() as JobRow[];
  }

  listAssets(): AssetRow[] {
    return this.db
      .query(
        `SELECT id, asset_key, asset_type, status, parent_asset_id, last_materialized_at
         FROM assets ORDER BY asset_key`,
      )
      .all() as AssetRow[];
  }

  listJobRuns(limit = 50): JobRunRow[] {
    return this.db
      .query(
        `SELECT id, job_id, status, started_at, finished_at
         FROM job_runs ORDER BY created_at DESC LIMIT ?`,
      )
      .all(limit) as JobRunRow[];
  }

  listLogs(limit = 50): LogRow[] {
    return this.db
      .query(
        `SELECT id, job_run_id, log_kind, path FROM logs ORDER BY created_at DESC LIMIT ?`,
      )
      .all(limit) as LogRow[];
  }

  close(): void {
    this.db.close();
  }
}

export function openControlDb(path: string): ControlDb {
  return new ControlDb(path);
}
