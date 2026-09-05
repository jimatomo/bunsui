import { describe, expect, test } from "bun:test";
import { createApp } from "../src/app";
import {
  inferStatusFromOutput,
  isUnknownJobError,
  parseRunIdFromOutput,
  type RunJobFn,
} from "../src/runJob";

describe("runJob helpers", () => {
  test("parseRunIdFromOutput takes the last run_id", () => {
    const text = [
      "Running chain: a → b",
      "Job 'a' succeeded (run_id=11111111-1111-1111-1111-111111111111)",
      "Job 'b' succeeded (run_id=22222222-2222-2222-2222-222222222222)",
    ].join("\n");
    expect(parseRunIdFromOutput(text)).toBe(
      "22222222-2222-2222-2222-222222222222",
    );
  });

  test("inferStatusFromOutput and unknown-job detection", () => {
    expect(inferStatusFromOutput(0, "Job 'x' succeeded (run_id=abc)", "")).toBe(
      "succeeded",
    );
    expect(
      inferStatusFromOutput(
        0,
        "Job 'x' started (run_id=abc, status=running)",
        "",
      ),
    ).toBe("running");
    expect(
      inferStatusFromOutput(1, "", "Error: Job 'x' failed (run_id=abc): boom"),
    ).toBe("failed");
    expect(isUnknownJobError("job 'missing' not found in SQLite")).toBe(true);
    expect(isUnknownJobError("something else")).toBe(false);
  });
});

describe("POST /api/jobs/:name/run", () => {
  test("happy path returns run status and run_id", async () => {
    const runJob: RunJobFn = async ({ name, noDeps }) => ({
      ok: true,
      job: name,
      status: "succeeded",
      run_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      no_deps: Boolean(noDeps),
      exit_code: 0,
      stdout: `Job '${name}' succeeded (run_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee)`,
      stderr: "",
    });

    const app = createApp({
      sqlitePath: null,
      projectRoot: "/tmp/project",
      runJob,
    });
    const res = await app.request("/api/jobs/demo/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ no_deps: false }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.job).toBe("demo");
    expect(body.status).toBe("succeeded");
    expect(body.run_id).toBe("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
    expect(body.no_deps).toBe(false);
  });

  test("unknown job returns 404", async () => {
    const runJob: RunJobFn = async ({ name, noDeps }) => ({
      ok: false,
      job: name,
      status: "error",
      run_id: null,
      no_deps: Boolean(noDeps),
      error: `job '${name}' not found in SQLite (run \`bunsui job sync\` or check the name)`,
      exit_code: 1,
      stdout: "",
      stderr: `Error: job '${name}' not found in SQLite (run \`bunsui job sync\` or check the name)`,
    });

    const app = createApp({
      sqlitePath: null,
      projectRoot: "/tmp/project",
      runJob,
    });
    const res = await app.request("/api/jobs/missing/run", { method: "POST" });
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain("not found");
  });

  test("missing BUNSUI_PROJECT returns 503", async () => {
    const app = createApp({ sqlitePath: null, projectRoot: "" });
    const res = await app.request("/api/jobs/demo/run", { method: "POST" });
    expect(res.status).toBe(503);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain("BUNSUI_PROJECT");
  });

  test("invalid job name returns 400", async () => {
    const app = createApp({
      sqlitePath: null,
      projectRoot: "/tmp/project",
      runJob: async () => {
        throw new Error("should not be called");
      },
    });
    const res = await app.request("/api/jobs/-bad/run", { method: "POST" });
    expect(res.status).toBe(400);
  });

  test("no_deps is forwarded from JSON body", async () => {
    let seen: boolean | undefined;
    const runJob: RunJobFn = async ({ noDeps }) => {
      seen = noDeps;
      return {
        ok: true,
        job: "demo",
        status: "succeeded",
        run_id: "r1",
        no_deps: Boolean(noDeps),
        exit_code: 0,
        stdout: "",
        stderr: "",
      };
    };
    const app = createApp({
      sqlitePath: null,
      projectRoot: "/tmp/project",
      runJob,
    });
    const res = await app.request("/api/jobs/demo/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ no_deps: true }),
    });
    expect(res.status).toBe(200);
    expect(seen).toBe(true);
    const body = await res.json();
    expect(body.no_deps).toBe(true);
  });
});
