import type { HealthResponse } from "../api/types";

interface BackendStatusProps {
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
}

function BackendStatus({ health, loading, error }: BackendStatusProps) {
  const online = Boolean(health) && !error;

  return (
    <section className="panel status-panel" aria-labelledby="backend-status-heading">
      <div className="panel__header">
        <h2 id="backend-status-heading">Backend Status</h2>
        <span className={`status-pill ${online ? "status-pill--online" : "status-pill--offline"}`}>
          {loading ? "Connecting" : online ? "Online" : "Offline"}
        </span>
      </div>
      <div className="kv-grid">
        <div>
          <span className="kv-label">Service</span>
          <span className="kv-value">{health?.service ?? "Unavailable"}</span>
        </div>
        <div>
          <span className="kv-label">Version</span>
          <span className="kv-value">{health?.version ?? "Unknown"}</span>
        </div>
        <div>
          <span className="kv-label">Mode</span>
          <span className="kv-value">{health?.mode ?? "Disconnected"}</span>
        </div>
        <div>
          <span className="kv-label">Status</span>
          <span className="kv-value">{health?.status ?? "offline"}</span>
        </div>
      </div>
      {error ? <p className="status-error">{error}</p> : null}
    </section>
  );
}

export default BackendStatus;
