import { motion, useReducedMotion } from "framer-motion";

interface DecisionStampProps {
  decision: string;
}

function stampTone(decision: string): "allow" | "warn" | "deny" {
  if (decision === "ALLOW") {
    return "allow";
  }
  if (decision === "FREEZE" || decision === "ESCALATE") {
    return "warn";
  }
  return "deny";
}

function DecisionStamp({ decision }: DecisionStampProps) {
  const shouldReduceMotion = useReducedMotion();
  const tone = stampTone(decision);

  return (
    <motion.div
      key={decision}
      className={`decision-stamp decision-stamp--${tone}`}
      data-testid="decision-stamp"
      initial={shouldReduceMotion ? false : { opacity: 0, scale: 1.18, rotate: -4 }}
      animate={{ opacity: 1, scale: 1, rotate: 0 }}
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.22, ease: "easeOut" }}
    >
      <svg className="decision-stamp__ring" viewBox="0 0 120 120" fill="none" aria-hidden="true">
        <circle cx="60" cy="60" r="52" stroke="currentColor" strokeWidth="2" strokeOpacity="0.35" />
        <circle cx="60" cy="60" r="42" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.55" />
        {Array.from({ length: 8 }, (_, index) => (
          <ellipse
            key={`stamp-ring-${index}`}
            cx="60"
            cy="60"
            rx="46"
            ry="22"
            transform={`rotate(${index * 22.5} 60 60)`}
            stroke="currentColor"
            strokeWidth="1"
            strokeOpacity="0.22"
          />
        ))}
      </svg>
      <span className="decision-stamp__label">{decision === "ALLOW" ? "CLEARED" : decision}</span>
    </motion.div>
  );
}

export default DecisionStamp;
