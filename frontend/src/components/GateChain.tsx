import { motion, useReducedMotion } from "framer-motion";

import type { RunGateState } from "../run/store";

interface GateChainProps {
  gates: RunGateState[];
}

const GATE_LABELS: Record<string, string> = {
  G1_EVIDENCE: "G1 Evidence",
  G2_GROUNDEDNESS: "G2 Groundedness",
  G3_POLICY: "G3 Policy",
  G4_RISK: "G4 Risk",
  G5_REALITY: "G5 Reality"
};

function gateNodeClass(status: RunGateState["status"]): string {
  switch (status) {
    case "PASS":
      return "gate-node--pass";
    case "WARN":
    case "FAIL":
      return "gate-node--fail";
    case "active":
      return "gate-node--running";
    default:
      return "gate-node--idle";
  }
}

function GateChain({ gates }: GateChainProps) {
  const shouldReduceMotion = useReducedMotion();
  const completed = gates.filter((gate) => gate.status === "PASS" || gate.status === "WARN" || gate.status === "FAIL");

  return (
    <section className="panel" aria-labelledby="gate-chain-heading">
      <div className="panel__header">
        <h2 id="gate-chain-heading">Gate Chain</h2>
        <span className="mono-label">{completed.length} completed</span>
      </div>
      <div className="gate-chain">
        {gates.map((gate, index) => {
          const delay = completed.findIndex((item) => item.id === gate.id);
          return (
            <motion.article
              key={gate.id}
              className={`gate-node ${gateNodeClass(gate.status)} ${gate.id === "G5_REALITY" ? "gate-node--featured" : ""}`}
              initial={shouldReduceMotion ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.24, delay: delay >= 0 ? delay * 0.15 : index * 0.05 }}
            >
              <div className="gate-node__header">
                <div>
                  <span className="kv-label mono-label">{gate.id}</span>
                  <h3>{GATE_LABELS[gate.id] ?? gate.id}</h3>
                </div>
                {gate.id === "G5_REALITY" ? <span className="badge badge--seal">Signature Gate</span> : null}
              </div>
              <div className="gate-node__body">
                <div>
                  <span className="kv-label">Status</span>
                  <span className="kv-value mono-value">
                    {gate.status === "active" ? "RUNNING" : gate.status.toUpperCase()}
                  </span>
                </div>
                <div>
                  <span className="kv-label">Reason code</span>
                  <span className="kv-value mono-value">{gate.reasonCode ?? "-"}</span>
                </div>
                <div>
                  <span className="kv-label">Human reason</span>
                  <span className="kv-value">{gate.humanReason ?? "-"}</span>
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
