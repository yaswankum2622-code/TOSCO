import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../../run/store";

interface MockBankExecutionCardProps {
  state: RunStoreState;
  onAttemptExecution: () => void;
}

function MockBankExecutionCard({ state, onAttemptExecution }: MockBankExecutionCardProps) {
  const shouldReduceMotion = useReducedMotion();

  if (state.bank === null) {
    return null;
  }

  const tone = state.bank.executed ? "allow" : "deny";

  return (
    <motion.section
      key={`${state.bank.executed}-${state.bank.reason}`}
      className={`panel right-card right-card--${tone}`}
      aria-labelledby="mock-bank-execution-heading"
      data-testid="mock-bank-execution-card"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.985 }}
      animate={
        shouldReduceMotion
          ? { opacity: 1, y: 0, scale: 1 }
          : tone === "deny"
            ? { opacity: 1, y: 0, scale: [0.985, 1.015, 1] }
            : { opacity: 1, y: 0, scale: [0.985, 1.008, 1] }
      }
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.22, ease: "easeOut" }}
    >
      <div className="panel__header">
        <h2 id="mock-bank-execution-heading">Mock Bank</h2>
        <span className={`status-pill status-pill--${tone}`}>
          {state.bank.executed ? "Executed" : "Rejected"}
        </span>
      </div>
      <div className="right-card__stack">
        <strong className={`decision-card__value decision-card__value--${tone}`}>
          {state.bank.executed ? "Executed - CLEARED" : `Rejected - ${state.bank.reason}`}
        </strong>
        <div className="right-card__mono-block">
          <span className="kv-label">Reason</span>
          <span className="mono-value" data-testid="bank-reason">
            {state.bank.reason}
          </span>
        </div>
      </div>
      <button className="ghost-button right-card__action" type="button" onClick={onAttemptExecution}>
        Attempt execution
      </button>
    </motion.section>
  );
}

export default MockBankExecutionCard;
