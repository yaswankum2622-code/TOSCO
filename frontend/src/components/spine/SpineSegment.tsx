import { motion, useReducedMotion } from "framer-motion";

import type { StationStatus } from "../../run/store";

interface SpineSegmentProps {
  fromId: string;
  resolvedStatus: StationStatus;
  shouldFill: boolean;
}

function segmentTone(status: StationStatus): "idle" | "pass" | "fail" {
  if (status === "pass") {
    return "pass";
  }
  if (status === "fail") {
    return "fail";
  }
  return "idle";
}

function SpineSegment({ fromId, resolvedStatus, shouldFill }: SpineSegmentProps) {
  const shouldReduceMotion = useReducedMotion();
  const tone = segmentTone(resolvedStatus);

  return (
    <div
      className={`spine-segment ${shouldFill ? "spine-segment--filled" : ""}`}
      data-testid={`spine-segment-${fromId}`}
      data-tone={tone}
      aria-hidden="true"
    >
      <div className="spine-segment__track" />
      <motion.div
        className={`spine-segment__fill spine-segment__fill--${tone}`}
        initial={false}
        animate={{
          opacity: shouldFill ? 1 : 0,
          scaleY: shouldFill ? 1 : 0
        }}
        transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2, ease: "easeOut" }}
      />
      {shouldFill ? <span className={`spine-segment__flow spine-segment__flow--${tone}`} /> : null}
    </div>
  );
}

export default SpineSegment;
