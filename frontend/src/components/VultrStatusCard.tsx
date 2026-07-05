import type { VultrStatusResponse } from "../api/types";

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
  const modeLabel = configured ? "Live extraction armed" : "Fallback rail armed";
  const readinessLabel = configured ? "Primary route" : "Fallback route";
  const readinessValue = configured ? "Online" : "Standby";

  return (
    <section
      className={`panel vultr-status-card ${configured ? "vultr-status-card--ready" : "vultr-status-card--fallback"}`}
      aria-labelledby="vultr-status-heading"
    >
      <div className="panel__header">
        <h2 id="vultr-status-heading">Live Extraction Link</h2>
        <span className={`status-pill ${configured ? "status-pill--online" : "status-pill--warning"}`}>
          {configured ? "Live ready" : "Fallback"}
        </span>
      </div>

      {error ? <p className="status-error status-error--compact">{error}</p> : null}

      <div className="vultr-status-card__stage" aria-hidden="true">
        <span className="vultr-status-card__stage-orb" />
        <span className="vultr-status-card__stage-ring vultr-status-card__stage-ring--a" />
        <span className="vultr-status-card__stage-ring vultr-status-card__stage-ring--b" />
        <span className="vultr-status-card__stage-line" />
      </div>

      <div className="kv-grid vultr-status-card__grid">
        <div>
          <span className="kv-label">State</span>
          <span className="kv-value">{loading ? "Checking live route" : modeLabel}</span>
        </div>
        <div>
          <span className="kv-label">{readinessLabel}</span>
          <span className="kv-value">{readinessValue}</span>
        </div>
        <div>
          <span className="kv-label">Fallback rail</span>
          <span className="kv-value">{configured ? "Ready behind live path" : "Primary path unavailable"}</span>
        </div>
        <div>
          <span className="kv-label">Source mark</span>
          <span className="kv-value">{configured ? "Vultr in spine extract step" : "Fallback label in spine extract step"}</span>
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
          ? "Live extraction is ready. Final clearance still belongs to deterministic TOSCO gates."
          : "Fallback mode stays safe. TOSCO can still complete the full run without breaking the clearance path."}
      </p>
    </section>
  );
}

export default VultrStatusCard;
