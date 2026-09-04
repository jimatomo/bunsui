import { useEffect, useState } from "react";

type Log = {
  id: string;
  job_run_id: string;
  log_kind: string;
  path: string | null;
};

type LogDetail = {
  id: string;
  content: string | null;
  error?: string;
};

export function LogsPage() {
  const [logs, setLogs] = useState<Log[] | null>(null);
  const [note, setNote] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LogDetail | null>(null);

  useEffect(() => {
    fetch("/api/logs")
      .then((r) => r.json())
      .then((body: { logs: Log[]; note?: string }) => {
        setLogs(body.logs ?? []);
        setNote(body.note ?? "");
      })
      .catch(() => setLogs([]));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    fetch(`/api/logs/${selectedId}`)
      .then((r) => r.json())
      .then((body: LogDetail) => {
        if (!cancelled) setDetail(body);
      })
      .catch(() => {
        if (!cancelled) {
          setDetail({ id: selectedId, content: null, error: "failed to load" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  return (
    <section>
      <h1>Logs</h1>
      <p className="lede">
        Stdout log paths tied to job runs. Select a row to read captured output.
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
              <tr
                key={l.id}
                onClick={() => setSelectedId(l.id)}
                style={{
                  cursor: "pointer",
                  background:
                    selectedId === l.id ? "var(--row-selected, #eee)" : undefined,
                }}
              >
                <td className="mono">{l.job_run_id}</td>
                <td>{l.log_kind}</td>
                <td className="mono">{l.path ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {selectedId && detail ? (
        <pre className="mono" style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
          {detail.error
            ? detail.error
            : (detail.content ?? "(empty)")}
        </pre>
      ) : null}
    </section>
  );
}
