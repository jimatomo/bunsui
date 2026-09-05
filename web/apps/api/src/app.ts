/**
 * Hono HTTP API for the React UI.
 *
 * Reads the bunsui SQLite control plane for job/asset status.
 * Job runs are triggered by spawning the Python CLI (`uv run bunsui job run`);
 * the engine owns writes (execution, DuckDB, schema init).
 * Async job completion is detected by polling SQLite status.
 */

import { readFileSync } from "node:fs";
import { isAbsolute, join } from "node:path";
import { Hono } from "hono";
import { cors } from "hono/cors";
import { openControlDb, type ControlDb } from "./db";
import {
  isUnknownJobError,
  runJobViaCli,
  type RunJobFn,
  type RunJobResult,
} from "./runJob";

const JOB_NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]*$/;

function resolveLogFilePath(
  projectRoot: string,
  path: string | null,
): string | null {
  if (!path) return null;
  if (isAbsolute(path)) return path;
  if (!projectRoot) return null;
  return join(projectRoot, path);
}

export type AppEnv = {
  Variables: {
    db: ControlDb | null;
    projectRoot: string;
  };
};

export function createApp(options?: {
  sqlitePath?: string | null;
  projectRoot?: string;
  /** Injected for tests; default spawns `uv run bunsui job run`. */
  runJob?: RunJobFn;
}): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  const projectRoot = options?.projectRoot ?? process.env.BUNSUI_PROJECT ?? "";
  const runJob: RunJobFn = options?.runJob ?? runJobViaCli;
  const sqlitePath =
    options?.sqlitePath === undefined
      ? process.env.BUNSUI_SQLITE ??
        (projectRoot ? `${projectRoot}/.bunsui/control.sqlite` : null)
      : options.sqlitePath;

  let db: ControlDb | null = null;
  try {
    if (sqlitePath) {
      db = openControlDb(sqlitePath);
    }
  } catch {
    db = null;
  }

  app.use("*", cors());

  app.use("*", async (c, next) => {
    c.set("db", db);
    c.set("projectRoot", projectRoot);
    await next();
  });

  app.get("/health", (c) =>
    c.json({
      ok: true,
      service: "bunsui-api",
      sqlite: db ? "connected" : "unavailable",
    }),
  );

  app.get("/api/status", (c) => {
    const control = c.get("db");
    if (!control) {
      return c.json(
        {
          ok: false,
          error: "SQLite control plane not available",
          hint: "Run `uv run bunsui init` and set BUNSUI_PROJECT or BUNSUI_SQLITE",
        },
        503,
      );
    }
    const counts = control.counts();
    return c.json({
      ok: true,
      sqlite_path: control.path,
      counts,
    });
  });

  app.get("/api/jobs", (c) => {
    const control = c.get("db");
    if (!control) {
      return c.json({ jobs: [], note: "sqlite unavailable" });
    }
    return c.json({ jobs: control.listJobs() });
  });

  app.post("/api/jobs/:name/run", async (c) => {
    const name = c.req.param("name");
    if (!JOB_NAME_RE.test(name)) {
      return c.json({ ok: false, error: "invalid job name" }, 400);
    }

    const root = c.get("projectRoot");
    if (!root) {
      return c.json(
        {
          ok: false,
          error: "BUNSUI_PROJECT is not set",
          hint: "export BUNSUI_PROJECT=/path/to/project",
        },
        503,
      );
    }

    let noDeps = false;
    const contentType = c.req.header("content-type") ?? "";
    if (contentType.includes("application/json")) {
      try {
        const body = (await c.req.json()) as { no_deps?: unknown };
        if (typeof body?.no_deps === "boolean") {
          noDeps = body.no_deps;
        }
      } catch {
        return c.json({ ok: false, error: "invalid JSON body" }, 400);
      }
    }

    let result: RunJobResult;
    try {
      result = await runJob({ name, projectRoot: root, noDeps });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return c.json(
        {
          ok: false,
          job: name,
          status: "error",
          run_id: null,
          no_deps: noDeps,
          error: message,
        },
        500,
      );
    }

    const payload = {
      ok: result.ok,
      job: result.job,
      status: result.status,
      run_id: result.run_id,
      no_deps: result.no_deps,
      error: result.error,
    };

    if (!result.ok && result.error && isUnknownJobError(result.error)) {
      return c.json(payload, 404);
    }
    if (!result.ok && result.status === "error" && result.exit_code === null) {
      return c.json(payload, 503);
    }
    // Execution finished (success, failure, or leaf async started).
    return c.json(payload);
  });

  app.get("/api/assets", (c) => {
    const control = c.get("db");
    if (!control) {
      return c.json({ assets: [], note: "sqlite unavailable" });
    }
    return c.json({ assets: control.listAssets() });
  });

  app.get("/api/runs", (c) => {
    const control = c.get("db");
    if (!control) {
      return c.json({ runs: [], note: "sqlite unavailable" });
    }
    return c.json({ runs: control.listJobRuns() });
  });

  app.get("/api/logs", (c) => {
    const control = c.get("db");
    if (!control) {
      return c.json({ logs: [], note: "sqlite unavailable" });
    }
    return c.json({
      logs: control.listLogs(),
      note: "GET /api/logs/:id returns captured stdout/stderr for a log row",
    });
  });

  app.get("/api/logs/:id", (c) => {
    const control = c.get("db");
    if (!control) {
      return c.json({ error: "SQLite control plane not available" }, 503);
    }
    const id = c.req.param("id");
    const row = control.getLog(id);
    if (!row) {
      return c.json({ error: "log not found" }, 404);
    }
    const filePath = resolveLogFilePath(c.get("projectRoot"), row.path);
    if (!filePath) {
      return c.json(
        {
          id: row.id,
          job_run_id: row.job_run_id,
          log_kind: row.log_kind,
          path: row.path,
          content: null,
          error: "log path could not be resolved (set BUNSUI_PROJECT)",
        },
        200,
      );
    }
    try {
      const content = readFileSync(filePath, "utf8");
      return c.json({
        id: row.id,
        job_run_id: row.job_run_id,
        log_kind: row.log_kind,
        path: row.path,
        content,
      });
    } catch {
      return c.json(
        {
          id: row.id,
          job_run_id: row.job_run_id,
          log_kind: row.log_kind,
          path: row.path,
          content: null,
          error: `log file not readable: ${filePath}`,
        },
        200,
      );
    }
  });

  return app;
}
