import { motion, useReducedMotion } from "framer-motion";

import type { RunSummaryResponse } from "../api/types";
import { decisionClass } from "../utils/format";

interface CounterfactualStripProps {
  run: RunSummaryResponse | null;
}

const COPY: Record<string, { without: string; with: string }> = {
  clean: {
    without: "Without TOSCO: payment would proceed.",
    with: "With TOSCO: payment cleared and token-bound."
  },
  injection: {
    without: "Without TOSCO: attacker-routed payment could be sent.",
    with: "With TOSCO: bank mismatch blocked before execution."
  },
  forgery: {
    without: "Without TOSCO: internally consistent forged documents could pass.",
    with: "With TOSCO: Reality Gate froze execution."
  }
};

function CounterfactualStrip({ run }: CounterfactualStripProps) {
  const shouldReduceMotion = useReducedMotion();
  const copy = run ? COPY[run.scenario] : undefined;

  return (
    <motion.section
      className={`panel counterfactual-strip ${decisionClass(run?.final_decision)}`}
      aria-labelledby="counterfactual-heading"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: 0.04 }}
    >
      <div className="panel__header">
        <h2 id="counterfactual-heading">Counterfactual</h2>
      </div>
      {!copy ? (
        <p className="empty-state">This strip frames the control story once a scenario run exists.</p>
      ) : (
        <div className="counterfactual-strip__rows">
          <p>{copy.without}</p>
          <p>{copy.with}</p>
        </div>
      )}
    </motion.section>
  );
}

export default CounterfactualStrip;
