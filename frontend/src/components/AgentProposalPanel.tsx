import { motion, useReducedMotion } from "framer-motion";

import type { EventTimelineResponse, RunSummaryResponse } from "../api/types";
import { formatMoney } from "../utils/format";
import { findEvent, payloadNumber, payloadString } from "../utils/timeline";

interface AgentProposalPanelProps {
  run: RunSummaryResponse | null;
  timeline: EventTimelineResponse | null;
}

function AgentProposalPanel({ run, timeline }: AgentProposalPanelProps) {
  const shouldReduceMotion = useReducedMotion();
  const event = findEvent(timeline?.events, "AGENT_PROPOSED");
  const payload = event?.payload;
  const scenario = payloadString(payload, "scenario") ?? run?.scenario;
  const naiveAction = payloadString(payload, "naive_action");
  const vendorId = payloadString(payload, "vendor_id");
  const amount = payloadNumber(payload, "amount");
  const bankAccountLast4 = payloadString(payload, "bank_account_last4");

  return (
    <motion.section
      className="panel"
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
      {!event ? (
        <p className="empty-state">The proposal payload appears after the backend emits AGENT_PROPOSED.</p>
      ) : (
        <div className="proposal-card">
          <div>
            <span className="kv-label">Naive action</span>
            <strong className="proposal-card__action">{naiveAction ?? "—"}</strong>
          </div>
          <div className="kv-grid">
            <div>
              <span className="kv-label">Vendor ID</span>
              <span className="kv-value">{vendorId ?? "—"}</span>
            </div>
            <div>
              <span className="kv-label">Amount</span>
              <span className="kv-value">{formatMoney(amount)}</span>
            </div>
            <div>
              <span className="kv-label">Bank account</span>
              <span className="kv-value">{bankAccountLast4 ? `•••• ${bankAccountLast4}` : "—"}</span>
            </div>
            <div>
              <span className="kv-label">Scenario</span>
              <span className="kv-value">{scenario ?? "—"}</span>
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

export default AgentProposalPanel;
