import { motion, useReducedMotion } from "framer-motion";

import { formatMoney } from "../utils/format";
import type { RunProposalState } from "../run/store";

interface AgentProposalPanelProps {
  proposal: RunProposalState | null;
}

function AgentProposalPanel({ proposal }: AgentProposalPanelProps) {
  const shouldReduceMotion = useReducedMotion();
  const request = proposal?.request ?? null;
  const scenario = request?.scenario ?? null;
  const amount = request ? formatMoney(request.action.amount, request.action.currency) : null;

  return (
    <motion.section
      className="panel agent-proposal-panel"
      aria-labelledby="agent-proposal-heading"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
    >
      <div className="panel__header">
        <h2 id="agent-proposal-heading">Reference AP Agent</h2>
        <span className="mono-label">{scenario ?? "Awaiting proposal"}</span>
      </div>
      <p className="panel__subcopy">The agent proposes. It does not clear.</p>
      {!request ? (
        <p className="empty-state">The proposal appears as soon as a scenario starts.</p>
      ) : (
        <div className="proposal-card">
          <div className="proposal-card__hero">
            <div className="proposal-card__hero-copy">
              <span className="kv-label">Intended move</span>
              <strong className="proposal-card__amount">{amount}</strong>
              <span className="proposal-card__route mono-value">
                {request.action.vendor_id} -&gt; .... {request.action.bank_account_last4}
              </span>
            </div>
            <div className="proposal-card__intent">
              <span className="kv-label">Intent</span>
              <strong className="proposal-card__action mono-value">{proposal?.intentId ?? "pending"}</strong>
            </div>
          </div>
          <div className="kv-grid">
            <div>
              <span className="kv-label">Vendor ID</span>
              <span className="kv-value mono-value">{request.action.vendor_id}</span>
            </div>
            <div>
              <span className="kv-label">Amount</span>
              <span className="kv-value mono-value">{amount}</span>
            </div>
            <div>
              <span className="kv-label">Bank account</span>
              <span className="kv-value mono-value">{`.... ${request.action.bank_account_last4}`}</span>
            </div>
            <div>
              <span className="kv-label">Scenario</span>
              <span className="kv-value mono-value">{scenario}</span>
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

export default AgentProposalPanel;
