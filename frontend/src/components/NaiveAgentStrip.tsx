import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../run/store";

interface NaiveAgentStripProps {
  state: RunStoreState;
}

function NaiveAgentStrip({ state }: NaiveAgentStripProps) {
  const shouldReduceMotion = useReducedMotion();

  if (state.scenario !== "injection" || state.proposal === null) {
    return null;
  }

  const action = state.proposal.request.action;

  return (
    <motion.section
      className="naive-agent-strip"
      aria-label="Naive agent approval strip"
      data-testid="naive-agent-strip"
      initial={shouldReduceMotion ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.18 }}
    >
      <span className="naive-agent-strip__label">Naive agent</span>
      <span className="naive-agent-strip__value">
        APPROVED -&gt; attacker account .... {action.bank_account_last4}
      </span>
    </motion.section>
  );
}

export default NaiveAgentStrip;
