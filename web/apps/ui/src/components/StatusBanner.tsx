import { useEffect, useState } from "react";

type StatusPayload = {
  ok: boolean;
  sqlite_path?: string;
  counts?: Record<string, number>;
  error?: string;
  hint?: string;
};

export function StatusBanner() {
  const [status, setStatus] = useState<StatusPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/status");
        const body = (await res.json()) as StatusPayload;
        if (!cancelled) setStatus(body);
      } catch {
        if (!cancelled) {
          setStatus({
            ok: false,
            error: "API unreachable",
            hint: "Start the API with bun run dev:api (port 8787)",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status) {
    return <div className="banner">Connecting to control plane…</div>;
  }

  if (!status.ok) {
    return (
      <div className="banner">
        SQLite: unavailable — {status.error}
        {status.hint ? ` (${status.hint})` : ""}
      </div>
    );
  }

  const c = status.counts ?? {};
  return (
    <div className="banner">
      Control plane <strong>ok</strong> · jobs {c.jobs ?? 0} · assets{" "}
      {c.assets ?? 0} · runs {c.job_runs ?? 0}
    </div>
  );
}
