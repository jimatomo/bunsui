/**
 * Hono HTTP API for the React UI.
 *
 * Reads the bunsui SQLite control plane for job/asset status.
 * The Python engine owns writes (execution, DuckDB, schema init).
 * Async job completion is detected by polling SQLite status.
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import { openControlDb, type ControlDb } from "./db";

export type AppEnv = {
  Variables: {
    db: ControlDb | null;
    projectRoot: string;
  };
};

export function createApp(options?: {
  sqlitePath?: string | null;
  projectRoot?: string;
}): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  const projectRoot = options?.projectRoot ?? process.env.BUNSUI_PROJECT ?? "";
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
      note: "Log tailing is not implemented yet",
    });
  });

  return app;
}
