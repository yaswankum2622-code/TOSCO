import type { RunSummaryResponse, VerifyRunResponse } from "../api/types";
import HashDisplay from "./HashDisplay";
import { yesNo } from "../utils/format";

interface ProofVerifierProps {
  run: RunSummaryResponse | null;
  verification: VerifyRunResponse | null;
  onVerify: () => void;
  onTamper: () => void;
}

function ProofVerifier({ run, verification, onVerify, onTamper }: ProofVerifierProps) {
  const disabled = run === null;

  return (
    <section className="panel verifier-panel" aria-labelledby="proof-verifier-heading">
      <div className="panel__header">
        <h2 id="proof-verifier-heading">Proof Verifier</h2>
        <span className={`status-pill ${verification?.verified ? "status-pill--online" : "status-pill--warning"}`}>
          {verification ? (verification.verified ? "Verified" : "Compromised") : "Awaiting check"}
        </span>
      </div>
      <div className="hash-stack hash-stack--compact">
        <HashDisplay label="Proof hash" value={run?.proof_hash} />
        <HashDisplay label="Ledger hash" value={run?.ledger_entry_hash} />
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
          <span className="kv-value">{verification ? yesNo(verification.ledger_chain_valid) : "—"}</span>
        </div>
        <div>
          <span className="kv-label">Packet entry valid</span>
          <span className="kv-value">{verification ? yesNo(verification.packet_entry_valid) : "—"}</span>
        </div>
      </div>
      <div className="button-row">
        <button className="primary-button" type="button" onClick={onVerify} disabled={disabled}>
          Verify Proof
        </button>
        <button className="ghost-button" type="button" onClick={onTamper} disabled={disabled}>
          Tamper Demo
        </button>
      </div>
    </section>
  );
}

export default ProofVerifier;
