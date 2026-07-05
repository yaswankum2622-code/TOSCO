import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../../run/store";
import { deriveDecisionHumanReason, deriveDecisionReasonCodes, decisionTone } from "./rightUtils";

interface DecisionCardProps {
  state: RunStoreState;
}

function DecisionCard({ state }: DecisionCardProps) {
  const shouldReduceMotion = useReducedMotion();

  if (state.decision === null) {
    return null;
  }

  const tone = decisionTone(state.decision.value);
  const reasonCodes = deriveDecisionReasonCodes(state);
  const humanReason = deriveDecisionHumanReason(state);

  return (
    <motion.section
      key={state.decision.value}
      className={`panel right-card right-card--decision right-card--${tone}`}
      aria-labelledby="decision-card-heading"
      data-testid="decision-card"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.98 }}
      animate={
        shouldReduceMotion
          ? { opacity: 1, y: 0, scale: 1 }
          : tone === "deny"
            ? { opacity: 1, y: 0, scale: [0.98, 1.02, 1] }
            : { opacity: 1, y: 0, scale: [0.98, 1.01, 1] }
      }
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.24, ease: "easeOut" }}
    >
      <div className="panel__header">
        <h2 id="decision-card-heading">Decision</h2>
        <span className={`status-pill status-pill--${tone}`}>{state.decision.value}</span>
      </div>
      <strong className={`decision-card__value decision-card__value--${tone}`}>{state.decision.value}</strong>
      <p className="panel__subcopy">{humanReason}</p>
      {reasonCodes.length > 0 ? (
        <div className="right-card__mono-block">
          <span className="kv-label">Reason codes</span>
          <span className="mono-value" data-testid="decision-reason-codes">
            {reasonCodes.join(" | ")}
          </span>
        </div>
      ) : null}
    </motion.section>
  );
}

export default DecisionCard;
