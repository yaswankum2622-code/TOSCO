import { motion, useReducedMotion } from "framer-motion";

import type { RunBankState, RunTokenState } from "../run/store";
import { yesNo } from "../utils/format";

interface MockBankCardProps {
  bank: RunBankState | null;
  token: RunTokenState | null;
}

function MockBankCard({ bank, token }: MockBankCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const accepted = bank?.executed ?? false;
  const hasResult = bank !== null;

  return (
    <motion.section
      className={`panel mock-bank-card ${accepted ? "decision-allow" : hasResult ? "decision-block" : "decision-neutral"}`}
      aria-labelledby="mock-bank-heading"
      initial={shouldReduceMotion ? false : { opacity: 0, scale: 0.98 }}
      animate={hasResult && !shouldReduceMotion ? { opacity: 1, scale: [1, 1.015, 1] } : { opacity: 1, scale: 1 }}
      transition={{ duration: 0.28 }}
    >
      <div className="panel__header">
        <h2 id="mock-bank-heading">Mock Bank</h2>
        <span className="mono-label">{hasResult ? (accepted ? "ACCEPTED" : "REJECTED") : "Awaiting execution"}</span>
      </div>
      <p className="panel__subcopy">Execution obeys the clearance token.</p>
      {!hasResult ? (
        <p className="empty-state">Execution state appears after the backend emits EXECUTION_ATTEMPTED.</p>
      ) : (
        <div className="kv-grid">
          <div>
            <span className="kv-label">Token issued</span>
            <span className="kv-value mono-value">{yesNo(token?.issued)}</span>
          </div>
          <div>
            <span className="kv-label">Execution attempted</span>
            <span className="kv-value mono-value">Yes</span>
          </div>
          <div>
            <span className="kv-label">Accepted</span>
            <span className="kv-value mono-value">{yesNo(accepted)}</span>
          </div>
          <div>
            <span className="kv-label">Reason code</span>
            <span className="kv-value mono-value">{bank.reason}</span>
          </div>
        </div>
      )}
    </motion.section>
  );
}

export default MockBankCard;
