import { NavLink, Route, Routes } from "react-router-dom";
import { AssetsPage } from "./pages/AssetsPage";
import { JobsPage } from "./pages/JobsPage";
import { LogsPage } from "./pages/LogsPage";
import { StatusBanner } from "./components/StatusBanner";

export default function App() {
  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="brand-mark">bunsui</span>
          <span className="brand-sub">local data platform</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            Jobs
          </NavLink>
          <NavLink to="/assets">Assets</NavLink>
          <NavLink to="/logs">Logs</NavLink>
        </nav>
      </header>
      <StatusBanner />
      <main className="main">
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/logs" element={<LogsPage />} />
        </Routes>
      </main>
    </div>
  );
}
