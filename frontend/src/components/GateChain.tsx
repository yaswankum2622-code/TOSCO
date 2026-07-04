import { motion, useReducedMotion } from "framer-motion";

import type { EventTimelineResponse } from "../api/types";
import { findEvents, findGateCompleted, payloadString } from "../utils/timeline";

interface GateChainProps {
  timeline: EventTimelineResponse | null;
}

const GATES = [
  { gateId: "G1_EVIDENCE", label: "G1 Evidence" },
  { gateId: "G2_GROUNDEDNESS", label: "G2 Groundedness" },
  { gateId: "G3_POLICY", label: "G3 Policy" },
  { gateId: "G4_RISK", label: "G4 Risk" },
  { gateId: "G5_REALITY", label: "G5 Reality", featured: true },
  { gateId: "G6_DECISION_SEAL", label: "G6 Decision Seal" }
];

function GateChain({ timeline }: GateChainProps) {
  const shouldReduceMotion = useReducedMotion();
  const startedEvents = findEvents(timeline?.events, "GATE_STARTED");
  const completedEvents = findEvents(timeline?.events, "GATE_COMPLETED");

  return (
    <section className="panel" aria-labelledby="gate-chain-heading">
      <div className="panel__header">
        <h2 id="gate-chain-heading">Gate Chain</h2>
        <span className="mono-label">{completedEvents.length} completed</span>
      </div>
      <div className="gate-chain">
        {GATES.map((gate, gateIndex) => {
          const completed = findGateCompleted(timeline?.events, gate.gateId);
          const started = startedEvents.find(
            (event) => payloadString(event.payload, "gate_id") === gate.gateId
          );
          const status = payloadString(completed?.payload, "status");
          const decision = payloadString(completed?.payload, "decision");
          const reasonCode = payloadString(completed?.payload, "reason_code");
          const stateClass = completed
            ? status === "PASS"
              ? "gate-node--pass"
              : status === "WARN"
                ? "gate-node--warn"
                : "gate-node--fail"
            : started
              ? "gate-node--running"
              : "gate-node--idle";
          const animationIndex = completedEvents.findIndex((event) => event === completed);
          const delay = animationIndex >= 0 ? animationIndex * 0.15 : gateIndex * 0.05;

          return (
            <motion.article
              key={gate.gateId}
              className={`gate-node ${stateClass} ${gate.featured ? "gate-node--featured" : ""}`}
              initial={shouldReduceMotion ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.24, delay }}
            >
              <div className="gate-node__header">
                <div>
                  <span className="kv-label">{gate.gateId}</span>
                  <h3>{gate.label}</h3>
                </div>
                {gate.featured ? <span className="badge badge--seal">Signature Gate</span> : null}
              </div>
              <div className="gate-node__body">
                <div>
                  <span className="kv-label">Status</span>
                  <span className="kv-value">{status ?? (started ? "RUNNING" : "IDLE")}</span>
                </div>
                <div>
                  <span className="kv-label">Decision</span>
                  <span className="kv-value">{decision ?? "-"}</span>
                </div>
                <div>
                  <span className="kv-label">Reason code</span>
                  <span className="kv-value">{reasonCode ?? "-"}</span>
                </div>
              </div>
            </motion.article>
          );
        })}
      </div>
    </section>
  );
}

export default GateChain;
