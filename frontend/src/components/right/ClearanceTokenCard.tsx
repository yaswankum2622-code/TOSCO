import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../../run/store";

interface ClearanceTokenCardProps {
  state: RunStoreState;
}

function ClearanceTokenCard({ state }: ClearanceTokenCardProps) {
  const shouldReduceMotion = useReducedMotion();

  if (state.token === null && state.decision === null) {
    return null;
  }

  if (state.token === null && state.decision?.value === "ALLOW") {
    return null;
  }

  const hasToken = state.token?.issued === true;
  const tone = hasToken ? "allow" : "warn";

  return (
    <motion.section
      className={`panel right-card right-card--${tone}`}
      aria-labelledby="clearance-token-heading"
      data-testid="token-card"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.2, ease: "easeOut" }}
    >
      <div className="panel__header">
        <h2 id="clearance-token-heading">Clearance Token</h2>
        <span className={`status-pill ${hasToken ? "status-pill--allow" : ""}`}>
          {hasToken ? "Issued" : "Not issued"}
        </span>
      </div>
      {!hasToken ? (
        <p className="empty-state">No clearance token issued.</p>
      ) : (
        <div className="right-card__stack">
          <p className="panel__subcopy">Token issued.</p>
          <div className="right-card__mono-block">
            <span className="kv-label">Token</span>
            <span className="mono-value" data-testid="token-value">
              {state.token?.tokenShort}
            </span>
          </div>
          <div className="right-card__mono-block">
            <span className="kv-label">Exp</span>
            <span className="mono-value">{state.token?.exp ?? "-"}</span>
          </div>
        </div>
      )}
    </motion.section>
  );
}

export default ClearanceTokenCard;
