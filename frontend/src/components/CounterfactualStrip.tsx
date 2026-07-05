import { motion, useReducedMotion } from "framer-motion";

import { decisionClass, formatMoney } from "../utils/format";
import type { RunCounterfactualState, RunDecisionState } from "../run/store";

interface CounterfactualStripProps {
  counterfactual: RunCounterfactualState | null;
  decision: RunDecisionState | null;
  amount: number | null;
}

function CounterfactualStrip({ counterfactual, decision, amount }: CounterfactualStripProps) {
  const shouldReduceMotion = useReducedMotion();
  const isAlert = decision?.value === "BLOCK" || decision?.value === "FREEZE";

  if (!counterfactual || decision === null) {
    return null;
  }

  return (
    <motion.section
      className={`panel counterfactual-strip ${decisionClass(decision?.value)} ${isAlert ? "counterfactual-strip--alert" : ""}`}
      aria-labelledby="counterfactual-heading"
      data-testid="counterfactual-strip"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: 0.04 }}
    >
      <div className="panel__header">
        <h2 id="counterfactual-heading">Counterfactual</h2>
      </div>
      <div className="counterfactual-strip__rows">
        {decision?.value === "ALLOW" ? (
          <div className="counterfactual-strip__impact">
            <span className="counterfactual-strip__impact-label">Exposure prevented</span>
            <strong
              className="counterfactual-strip__amount mono-value"
              data-testid="counterfactual-amount"
            >
              $0 exposure
            </strong>
          </div>
        ) : isAlert && amount !== null ? (
          <div className="counterfactual-strip__impact">
            <span className="counterfactual-strip__impact-label">Would have moved</span>
            <motion.strong
              className="counterfactual-strip__amount mono-value"
              data-testid="counterfactual-amount"
              initial={shouldReduceMotion ? false : { opacity: 0, scale: 1.15 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2, ease: "easeOut" }}
            >
              {formatMoney(amount)}
            </motion.strong>
          </div>
        ) : null}
        <p>{counterfactual.loss}</p>
        <p>{counterfactual.narrative}</p>
      </div>
    </motion.section>
  );
}

export default CounterfactualStrip;
