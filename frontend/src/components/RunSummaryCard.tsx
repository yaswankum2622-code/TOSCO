import type { RunSummaryResponse } from "../api/types";

interface RunSummaryCardProps {
  run: RunSummaryResponse | null;
}

function shortenHash(value: string): string {
  return value.length > 16 ? `${value.slice(0, 10)}...${value.slice(-8)}` : value;
}

function decisionClassName(decision: string): string {
  switch (decision) {
    case "ALLOW":
      return "decision-card--allow";
    case "BLOCK":
      return "decision-card--block";
    case "FREEZE":
      return "decision-card--freeze";
    case "ESCALATE":
    case "REQUEST_MORE_EVIDENCE":
      return "decision-card--warn";
    default:
      return "decision-card--neutral";
  }
}

function RunSummaryCard({ run }: RunSummaryCardProps) {
  if (!run) {
    return (
      <section className="panel decision-card decision-card--neutral" aria-labelledby="run-summary-heading">
        <div className="panel__header">
          <h2 id="run-summary-heading">Run Summary</h2>
        </div>
        <p className="empty-state">Start a scenario to view the backend-computed run outcome.</p>
      </section>
    );
  }

  return (
    <section
      className={`panel decision-card ${decisionClassName(run.final_decision)}`}
      aria-labelledby="run-summary-heading"
    >
      <div className="panel__header">
        <h2 id="run-summary-heading">Run Summary</h2>
        <span className="mono-label">{run.scenario}</span>
      </div>
      <div className="decision-lockup">
        <span className="kv-label">Final decision</span>
        <strong className="decision-value" data-testid="final-decision">
          {run.final_decision}
        </strong>
      </div>
      <div className="kv-grid">
        <div>
          <span className="kv-label">Allow execution</span>
          <span className="kv-value">{run.allow_execution ? "true" : "false"}</span>
        </div>
        <div>
          <span className="kv-label">Token issued</span>
          <span className="kv-value">{run.token_issued ? "true" : "false"}</span>
        </div>
        <div>
          <span className="kv-label">Mock bank status</span>
          <span className="kv-value">{run.mock_bank_status}</span>
        </div>
        <div>
          <span className="kv-label">Reason code</span>
          <span className="kv-value">{run.mock_bank_reason_code}</span>
        </div>
      </div>
      <div className="hash-stack">
        <div>
          <span className="kv-label">Proof hash</span>
          <code title={run.proof_hash}>{shortenHash(run.proof_hash)}</code>
        </div>
        <div>
          <span className="kv-label">Ledger hash</span>
          <code title={run.ledger_entry_hash}>{shortenHash(run.ledger_entry_hash)}</code>
        </div>
        <div>
          <span className="kv-label">Run ID</span>
          <code title={run.run_id}>{run.run_id}</code>
        </div>
      </div>
    </section>
  );
}

export default RunSummaryCard;
