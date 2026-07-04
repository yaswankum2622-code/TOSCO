import { motion, useReducedMotion } from "framer-motion";

import type { EventTimelineResponse, RunSummaryResponse } from "../api/types";
import { yesNo } from "../utils/format";
import { extractExecutionFinalEvent, findEvent, payloadString } from "../utils/timeline";

interface MockBankCardProps {
  run: RunSummaryResponse | null;
  timeline: EventTimelineResponse | null;
}

function MockBankCard({ run, timeline }: MockBankCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const attemptedEvent = findEvent(timeline?.events, "EXECUTION_ATTEMPTED");
  const finalEvent = extractExecutionFinalEvent(timeline?.events);
  const accepted = finalEvent?.event_type === "EXECUTION_ACCEPTED";
  const reasonCode = payloadString(finalEvent?.payload, "reason_code") ?? run?.mock_bank_reason_code;
  const executionReference = payloadString(finalEvent?.payload, "execution_reference");

  return (
    <motion.section
      className={`panel mock-bank-card ${accepted ? "decision-allow" : finalEvent ? "decision-block" : "decision-neutral"}`}
      aria-labelledby="mock-bank-heading"
      initial={shouldReduceMotion ? false : { opacity: 0, scale: 0.98 }}
      animate={finalEvent && !shouldReduceMotion ? { opacity: 1, scale: [1, 1.015, 1] } : { opacity: 1, scale: 1 }}
      transition={{ duration: 0.28 }}
    >
      <div className="panel__header">
        <h2 id="mock-bank-heading">Mock Bank</h2>
        <span className="mono-label">{run?.mock_bank_status ?? "Awaiting execution"}</span>
      </div>
      <p className="panel__subcopy">Execution obeys the clearance token.</p>
      {!run ? (
        <p className="empty-state">Execution state appears after the backend attempts the sandbox rail.</p>
      ) : (
        <div className="kv-grid">
          <div>
            <span className="kv-label">Token issued</span>
            <span className="kv-value">{yesNo(run.token_issued)}</span>
          </div>
          <div>
            <span className="kv-label">Execution attempted</span>
            <span className="kv-value">{yesNo(Boolean(attemptedEvent))}</span>
          </div>
          <div>
            <span className="kv-label">Accepted</span>
            <span className="kv-value">{yesNo(accepted)}</span>
          </div>
          <div>
            <span className="kv-label">Reason code</span>
            <span className="kv-value">{reasonCode ?? "-"}</span>
          </div>
          <div>
            <span className="kv-label">Execution reference</span>
            <span className="kv-value">{executionReference ?? "-"}</span>
          </div>
        </div>
      )}
    </motion.section>
  );
}

export default MockBankCard;
