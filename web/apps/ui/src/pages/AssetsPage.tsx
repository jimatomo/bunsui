import { useEffect, useState } from "react";

type Asset = {
  id: string;
  asset_key: string;
  asset_type: string | null;
  status: string;
  parent_asset_id: string | null;
  last_materialized_at: string | null;
};

export function AssetsPage() {
  const [assets, setAssets] = useState<Asset[] | null>(null);

  useEffect(() => {
    fetch("/api/assets")
      .then((r) => r.json())
      .then((body: { assets: Asset[] }) => setAssets(body.assets ?? []))
      .catch(() => setAssets([]));
  }, []);

  return (
    <section>
      <h1>Asset status</h1>
      <p className="lede">
        Dagster-style status units. dbt tests will be children of their model
        via <span className="mono">parent_asset_id</span>.
      </p>
      {assets === null ? (
        <div className="empty">Loading…</div>
      ) : assets.length === 0 ? (
        <div className="empty">No assets yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Type</th>
              <th>Status</th>
              <th>Last</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.id}>
                <td className="mono">{a.asset_key}</td>
                <td>{a.asset_type ?? "—"}</td>
                <td>{a.status}</td>
                <td className="mono">{a.last_materialized_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
