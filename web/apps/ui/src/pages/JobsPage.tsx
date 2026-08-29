import { useEffect, useState } from "react";

type Job = {
  id: string;
  name: string;
  job_type: string;
  execution_mode: string;
  enabled: number;
};

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null);

  useEffect(() => {
    fetch("/api/jobs")
      .then((r) => r.json())
      .then((body: { jobs: Job[] }) => setJobs(body.jobs ?? []))
      .catch(() => setJobs([]));
  }, []);

  return (
    <section>
      <h1>Jobs</h1>
      <p className="lede">
        Execution units from <code>jobs/*.yaml</code> (or inline{" "}
        <code>jobs:</code>), synced with <code>bunsui job sync</code>. Running
        jobs is not implemented yet.
      </p>
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
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id}>
                <td className="mono">{j.name}</td>
                <td>{j.job_type}</td>
                <td>{j.execution_mode}</td>
                <td>{j.enabled ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
