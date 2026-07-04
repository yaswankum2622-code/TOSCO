import type { RunSummaryResponse, VerifyRunResponse } from "../api/types";
import { yesNo } from "../utils/format";

interface DemoControlPanelProps {
  activeRun: RunSummaryResponse | null;
  verification: VerifyRunResponse | null;
  onVerify: () => void;
  onTamper: () => void;
  onReset: () => void;
  loading: boolean;
}

function DemoControlPanel({
  activeRun,
  verification,
  onVerify,
  onTamper,
  onReset,
  loading
}: DemoControlPanelProps) {
  const disabled = activeRun === null || loading;

  return (
    <section className="panel demo-control-panel" aria-labelledby="demo-control-panel-heading">
      <div className="panel__header">
        <h2 id="demo-control-panel-heading">Demo Control Panel</h2>
        <span
          className={`status-pill ${
            verification ? (verification.verified ? "status-pill--online" : "status-pill--offline") : "status-pill--warning"
          }`}
        >
          {verification ? (verification.verified ? "Verified" : "Tampered") : "Awaiting proof"}
        </span>
      </div>
      <div className="kv-grid">
        <div>
          <span className="kv-label">Verified</span>
          <span className="kv-value" data-testid="verified-value">
            {verification ? String(verification.verified) : "not_checked"}
          </span>
        </div>
        <div>
          <span className="kv-label">Ledger chain valid</span>
          <span className="kv-value">{verification ? yesNo(verification.ledger_chain_valid) : "-"}</span>
        </div>
        <div>
          <span className="kv-label">Packet entry valid</span>
          <span className="kv-value">{verification ? yesNo(verification.packet_entry_valid) : "-"}</span>
        </div>
      </div>
      <div className="control-button-grid">
        <button className="primary-button control-button" type="button" onClick={onVerify} disabled={disabled}>
          Verify Proof
        </button>
        <button className="ghost-button control-button" type="button" onClick={onTamper} disabled={disabled}>
          Tamper Ledger
        </button>
        <button className="ghost-button control-button" type="button" onClick={onReset} disabled={loading}>
          Reset Demo
        </button>
      </div>
    </section>
  );
}

export default DemoControlPanel;
