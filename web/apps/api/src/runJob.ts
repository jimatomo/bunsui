/**
 * Trigger a job run by spawning the Python CLI.
 *
 * Choice: subprocess `uv run bunsui job run …` (not an in-process Python
 * import). Keeps the Hono API read-oriented for SQLite while reusing the
 * engine's dependency waves / fail-fast behavior unchanged. Blocking until
 * the chain finishes is intentional for this slice.
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

export type RunJobRequest = {
  name: string;
  projectRoot: string;
  noDeps?: boolean;
  /** Engine package directory (contains pyproject.toml). */
  engineDir?: string;
  /** Override binary resolution for tests. */
  uvBin?: string;
};

export type RunJobResult = {
  ok: boolean;
  job: string;
  status: "succeeded" | "failed" | "running" | "error";
  run_id: string | null;
  no_deps: boolean;
  error?: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
};

const RUN_ID_RE =
  /Job ['"](?<job>[^'"]+)['"] (?:succeeded|failed|started).*?\(run_id=(?<id>[0-9a-fA-F-]{8,})/g;

function defaultEngineDir(): string {
  // web/apps/api/src → repo root → engine
  return join(import.meta.dir, "../../../../engine");
}

function resolveUvBin(explicit?: string): string {
  if (explicit) return explicit;
  if (process.env.BUNSUI_UV) return process.env.BUNSUI_UV;
  return "uv";
}

export function parseRunIdFromOutput(text: string): string | null {
  let last: string | null = null;
  for (const match of text.matchAll(RUN_ID_RE)) {
    last = match.groups?.id ?? null;
  }
  return last;
}

export function inferStatusFromOutput(
  exitCode: number | null,
  stdout: string,
  stderr: string,
): RunJobResult["status"] {
  const combined = `${stdout}\n${stderr}`;
  if (/status=running/.test(combined) || / started \(run_id=/.test(combined)) {
    if (exitCode === 0) return "running";
  }
  if (exitCode === 0) return "succeeded";
  if (/ failed \(run_id=/.test(combined)) return "failed";
  return "error";
}

export function isUnknownJobError(message: string): boolean {
  return /job ['"].+['"] not found/i.test(message);
}

export async function runJobViaCli(
  req: RunJobRequest,
): Promise<RunJobResult> {
  const noDeps = Boolean(req.noDeps);
  const engineDir =
    req.engineDir ?? process.env.BUNSUI_ENGINE ?? defaultEngineDir();
  const uvBin = resolveUvBin(req.uvBin);

  if (!req.projectRoot) {
    return {
      ok: false,
      job: req.name,
      status: "error",
      run_id: null,
      no_deps: noDeps,
      error: "BUNSUI_PROJECT is not set",
      exit_code: null,
      stdout: "",
      stderr: "",
    };
  }

  if (!existsSync(join(engineDir, "pyproject.toml"))) {
    return {
      ok: false,
      job: req.name,
      status: "error",
      run_id: null,
      no_deps: noDeps,
      error: `engine directory not found or missing pyproject.toml: ${engineDir}`,
      exit_code: null,
      stdout: "",
      stderr: "",
    };
  }

  const args = [
    "run",
    "--directory",
    engineDir,
    "bunsui",
    "job",
    "run",
    req.name,
    "--project",
    req.projectRoot,
  ];
  if (noDeps) args.push("--no-deps");

  const { stdout, stderr, exitCode } = await spawnCapture(uvBin, args, {
    env: {
      ...process.env,
      BUNSUI_PROJECT: req.projectRoot,
    },
  });

  const combined = `${stdout}\n${stderr}`.trim();
  const status = inferStatusFromOutput(exitCode, stdout, stderr);
  const run_id = parseRunIdFromOutput(combined);
  const ok = status === "succeeded" || status === "running";
  let error: string | undefined;
  if (!ok) {
    const errLine =
      stderr
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .find((l) => l.startsWith("Error:") || /failed/i.test(l)) ??
      stderr.trim() ??
      stdout.trim();
    error = errLine.replace(/^Error:\s*/, "") || `job run exited ${exitCode}`;
  }

  return {
    ok,
    job: req.name,
    status,
    run_id,
    no_deps: noDeps,
    error,
    exit_code: exitCode,
    stdout,
    stderr,
  };
}

function spawnCapture(
  command: string,
  args: string[],
  options: { env: NodeJS.ProcessEnv },
): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      env: options.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", (err) => {
      reject(err);
    });
    child.on("close", (code) => {
      resolve({ stdout, stderr, exitCode: code });
    });
  });
}

export type RunJobFn = (req: RunJobRequest) => Promise<RunJobResult>;
