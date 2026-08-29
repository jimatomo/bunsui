import { useEffect, useState } from "react";

type Log = {
  id: string;
  job_run_id: string;
  log_kind: string;
  path: string | null;
};

export function LogsPage() {
  const [logs, setLogs] = useState<Log[] | null>(null);
  const [note, setNote] = useState<string>("");

  useEffect(() => {
    fetch("/api/logs")
      .then((r) => r.json())
      .then((body: { logs: Log[]; note?: string }) => {
        setLogs(body.logs ?? []);
        setNote(body.note ?? "");
      })
      .catch(() => setLogs([]));
  }, []);

  return (
    <section>
      <h1>Logs</h1>
      <p className="lede">
        Stdout log paths tied to job runs. Log tailing in the UI is not
        implemented yet.
      </p>
      {note ? <p className="lede mono">{note}</p> : null}
      {logs === null ? (
        <div className="empty">Loading…</div>
      ) : logs.length === 0 ? (
        <div className="empty">No logs yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Kind</th>
              <th>Path</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="mono">{l.job_run_id}</td>
                <td>{l.log_kind}</td>
                <td className="mono">{l.path ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
