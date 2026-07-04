import { motion, useReducedMotion } from "framer-motion";

import type { EventTimelineResponse, RunSummaryResponse } from "../api/types";
import { decisionClass, yesNo } from "../utils/format";
import { extractDecisionEvent, payloadString, payloadStringArray } from "../utils/timeline";

interface DecisionHeroProps {
  run: RunSummaryResponse | null;
  timeline: EventTimelineResponse | null;
}

const HEADLINES: Record<string, string> = {
  ALLOW: "CLEARED",
  BLOCK: "BLOCKED",
  FREEZE: "FROZEN",
  ESCALATE: "ESCALATED",
  REQUEST_MORE_EVIDENCE: "PENDING EVIDENCE"
};

function DecisionHero({ run, timeline }: DecisionHeroProps) {
  const shouldReduceMotion = useReducedMotion();
  const decisionEvent = extractDecisionEvent(timeline?.events);
  const status = payloadString(decisionEvent?.payload, "status");
  const reasonCodes = payloadStringArray(decisionEvent?.payload, "reason_codes");

  return (
    <motion.section
      key={run?.run_id ?? "decision-hero-empty"}
      className={`panel decision-hero ${decisionClass(run?.final_decision)}`}
      aria-labelledby="decision-hero-heading"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26 }}
    >
      <div className="panel__header">
        <h2 id="decision-hero-heading">Decision Hero</h2>
        <span className="mono-label">{status ?? "Awaiting verdict"}</span>
      </div>
      {!run ? (
        <p className="empty-state">The final decision appears when the backend finishes the clearance run.</p>
      ) : (
        <div className="decision-hero__content">
          <div className="decision-hero__lockup">
            <span className="decision-hero__headline">
              {HEADLINES[run.final_decision] ?? "PENDING"}
            </span>
            <strong className="decision-hero__verdict" data-testid="final-decision">
              {run.final_decision}
            </strong>
          </div>
          <div className="kv-grid">
            <div>
              <span className="kv-label">Allow execution</span>
              <span className="kv-value">{yesNo(run.allow_execution)}</span>
            </div>
            <div>
              <span className="kv-label">Mock bank status</span>
              <span className="kv-value">{run.mock_bank_status}</span>
            </div>
            <div>
              <span className="kv-label">Mock bank reason</span>
              <span className="kv-value">{run.mock_bank_reason_code}</span>
            </div>
            <div>
              <span className="kv-label">Reason codes</span>
              <span className="kv-value">{reasonCodes.join(", ") || "-"}</span>
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

export default DecisionHero;
