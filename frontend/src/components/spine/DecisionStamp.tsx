import { motion, useReducedMotion } from "framer-motion";

interface DecisionStampProps {
  decision: string;
}

function DecisionStamp({ decision }: DecisionStampProps) {
  const shouldReduceMotion = useReducedMotion();
  const isAllow = decision === "ALLOW";

  return (
    <motion.div
      key={decision}
      className={`decision-stamp ${isAllow ? "decision-stamp--allow" : "decision-stamp--deny"}`}
      data-testid="decision-stamp"
      initial={shouldReduceMotion ? false : { opacity: 0, scale: 1.18, rotate: -4 }}
      animate={{ opacity: 1, scale: 1, rotate: 0 }}
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.22, ease: "easeOut" }}
    >
      {isAllow ? "CLEARED" : decision}
    </motion.div>
  );
}

export default DecisionStamp;
