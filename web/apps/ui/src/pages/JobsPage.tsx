import { useCallback, useEffect, useState } from "react";

type Job = {
  id: string;
  name: string;
  job_type: string;
  execution_mode: string;
  enabled: number;
  last_run_status?: string | null;
  last_finished_at?: string | null;
};

type RunResponse = {
  ok: boolean;
  job?: string;
  status?: string;
  run_id?: string | null;
  error?: string;
};

type Flash = {
  kind: "ok" | "err";
  text: string;
};

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [flash, setFlash] = useState<Flash | null>(null);

  const loadJobs = useCallback(() => {
    return fetch("/api/jobs")
      .then((r) => r.json())
      .then((body: { jobs: Job[] }) => setJobs(body.jobs ?? []))
      .catch(() => setJobs([]));
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 5000);
    return () => window.clearTimeout(t);
  }, [flash]);

  async function runJob(name: string) {
    setRunning(name);
    setFlash(null);
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(name)}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ no_deps: false }),
      });
      const body = (await res.json()) as RunResponse;
      if (body.ok) {
        const status = body.status ?? "succeeded";
        setFlash({
          kind: "ok",
          text: `Run ${name}: ${status}${body.run_id ? ` (${body.run_id.slice(0, 8)}…)` : ""}`,
        });
      } else {
        setFlash({
          kind: "err",
          text: body.error ?? `Run ${name} failed`,
        });
      }
      await loadJobs();
    } catch {
      setFlash({ kind: "err", text: `Run ${name}: request failed` });
    } finally {
      setRunning(null);
    }
  }

  return (
    <section>
      <h1>Jobs</h1>
      <p className="lede">
        Execution units from <code>jobs/*.yaml</code> (or inline{" "}
        <code>jobs:</code>). Sync with <code>bunsui job sync</code>; use{" "}
        <strong>Run</strong> here or <code>bunsui job run &lt;name&gt;</code>{" "}
        (walks <code>depends_on</code> by default).
      </p>
      {flash ? (
        <div
          className={`flash ${flash.kind === "ok" ? "flash-ok" : "flash-err"}`}
          role="status"
        >
          {flash.text}
        </div>
      ) : null}
      {jobs === null ? (
        <div className="empty">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="empty">
          No jobs yet. Add <code>jobs/*.yaml</code> (or inline{" "}
          <code>jobs:</code>), then run <code>bunsui job sync</code>.
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Mode</th>
              <th>Enabled</th>
              <th>Last run</th>
              <th>Finished</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id}>
                <td className="mono">{j.name}</td>
                <td>{j.job_type}</td>
                <td>{j.execution_mode}</td>
                <td>{j.enabled ? "yes" : "no"}</td>
                <td>{j.last_run_status ?? "—"}</td>
                <td className="mono">{j.last_finished_at ?? "—"}</td>
                <td>
                  {j.enabled ? (
                    <button
                      type="button"
                      className="btn"
                      disabled={running === j.name}
                      onClick={() => void runJob(j.name)}
                    >
                      {running === j.name ? "Running…" : "Run"}
                    </button>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
