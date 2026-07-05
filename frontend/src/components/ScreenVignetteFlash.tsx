import { motion, useReducedMotion } from "framer-motion";

interface ScreenVignetteFlashProps {
  decision: string | null;
}

function ScreenVignetteFlash({ decision }: ScreenVignetteFlashProps) {
  const shouldReduceMotion = useReducedMotion();

  if (shouldReduceMotion || (decision !== "BLOCK" && decision !== "FREEZE")) {
    return null;
  }

  return (
    <motion.div
      key={decision}
      className="terminal-vignette-flash"
      data-testid="terminal-vignette-flash"
      aria-hidden="true"
      initial={{ opacity: 0 }}
      animate={{ opacity: [0, 0.9, 0.28, 0] }}
      transition={{ duration: 0.42, times: [0, 0.22, 0.58, 1], ease: "easeOut" }}
    />
  );
}

export default ScreenVignetteFlash;
