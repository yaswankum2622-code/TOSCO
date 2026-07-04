import type { VultrStatusResponse } from "../api/types";
import { yesNo } from "../utils/format";

interface VultrStatusCardProps {
  status: VultrStatusResponse | null;
  loading: boolean;
  error: string | null;
  useVultr: boolean;
  onToggleUseVultr: (value: boolean) => void;
}

function VultrStatusCard({
  status,
  loading,
  error,
  useVultr,
  onToggleUseVultr
}: VultrStatusCardProps) {
  const configured = status?.configured ?? false;
  const keyPresent = status?.key_present ?? false;

  return (
    <section
      className={`panel vultr-status-card ${configured ? "vultr-status-card--ready" : "vultr-status-card--fallback"}`}
      aria-labelledby="vultr-status-heading"
    >
      <div className="panel__header">
        <h2 id="vultr-status-heading">Vultr Serverless Inference</h2>
        <span className={`status-pill ${configured ? "status-pill--online" : "status-pill--warning"}`}>
          {configured ? "Configured" : "Fallback"}
        </span>
      </div>

      {error ? <p className="status-error status-error--compact">{error}</p> : null}

      <div className="kv-grid">
        <div>
          <span className="kv-label">Mode</span>
          <span className="kv-value">{status?.mode ?? (loading ? "loading" : "unavailable")}</span>
        </div>
        <div>
          <span className="kv-label">Configured</span>
          <span className="kv-value">{yesNo(configured)}</span>
        </div>
        <div>
          <span className="kv-label">Key present</span>
          <span className="kv-value">{yesNo(keyPresent)}</span>
        </div>
        <div>
          <span className="kv-label">Model</span>
          <span className="kv-value">{status?.model ?? (loading ? "loading" : "-")}</span>
        </div>
        <div className="vultr-status-card__wide">
          <span className="kv-label">Base URL</span>
          <span className="kv-value">{status?.base_url ?? (loading ? "loading" : "-")}</span>
        </div>
      </div>

      <label className="toggle-row">
        <input
          type="checkbox"
          checked={useVultr}
          disabled={loading}
          onChange={(event) => onToggleUseVultr(event.target.checked)}
        />
        <span>Use Vultr extraction for next run</span>
      </label>

      <p className="panel__subcopy">
        {configured
          ? "Vultr extraction ready. Final clearance still belongs to deterministic TOSCO gates."
          : "Fallback mode active. TOSCO will use seeded extraction while preserving deterministic gates."}
      </p>
    </section>
  );
}

export default VultrStatusCard;
