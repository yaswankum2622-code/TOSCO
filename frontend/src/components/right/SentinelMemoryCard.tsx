import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../../run/store";
import {
  decisionTone,
  deriveDecisionReasonCodes,
  deriveFailedSignals,
  failedOrWarnedGates
} from "./rightUtils";

interface SentinelMemoryCardProps {
  state: RunStoreState;
}

function SentinelMemoryCard({ state }: SentinelMemoryCardProps) {
  const shouldReduceMotion = useReducedMotion();

  if (state.decision === null || state.decision.value === "ALLOW") {
    return null;
  }

  const reasonCodes = deriveDecisionReasonCodes(state);
  const failedSignals = deriveFailedSignals(state);
  const tone = decisionTone(state.decision.value);

  return (
    <motion.section
      key={`${state.decision.value}-${reasonCodes.join("|")}`}
      className={`panel right-card right-card--${tone}`}
      aria-labelledby="sentinel-memory-heading"
      data-testid="sentinel-card"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 14, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.22, ease: "easeOut" }}
    >
      <div className="panel__header">
        <h2 id="sentinel-memory-heading">Sentinel Memory</h2>
        <span className="status-pill status-pill--deny">Recorded</span>
      </div>
      <p className="panel__subcopy">Sentinel recorded attack pattern.</p>
      <div className="right-card__stack">
        <div className="right-card__mono-block">
          <span className="kv-label">Reason codes</span>
          <span className="mono-value">
            {reasonCodes.join(" | ") || "-"}
          </span>
        </div>
        <div className="right-card__mono-block">
          <span className="kv-label">Failed signals</span>
          <span className="mono-value">
            {failedSignals.join(" | ") || "-"}
          </span>
        </div>
        {failedOrWarnedGates(state).length > 0 ? (
          <div className="right-card__mono-block">
            <span className="kv-label">Human reasons</span>
            <span className="mono-value">
              {failedOrWarnedGates(state)
                .map((gate) => gate.humanReason ?? "-")
                .join(" | ")}
            </span>
          </div>
        ) : null}
      </div>
    </motion.section>
  );
}

export default SentinelMemoryCard;
