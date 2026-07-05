import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../../run/store";
import { shortHash } from "../../utils/format";
import { downloadProofPacketPdf } from "../../utils/proofPdf";

interface ProofPacketViewerProps {
  state: RunStoreState;
}

function ProofPacketViewer({ state }: ProofPacketViewerProps) {
  const shouldReduceMotion = useReducedMotion();
  const [open, setOpen] = useState(false);

  if (state.proof?.sealed !== true || state.proof.chainHash === null || state.proposal === null) {
    return null;
  }

  const packetRows = [
    { label: "Run", value: state.runId ?? "-" },
    { label: "Workflow", value: state.workflow ?? "-" },
    { label: "Scenario", value: state.scenario ?? "-" },
    { label: "Intent", value: state.proposal.intentId ?? "-" },
    { label: "Decision", value: state.decision?.value ?? "-" },
    { label: "Token", value: state.token?.tokenShort ?? "Not issued" },
    { label: "Bank", value: state.bank ? `${state.bank.executed ? "Executed" : "Rejected"} | ${state.bank.reason}` : "Pending" }
  ];

  return (
    <motion.section
      className="panel right-card proof-packet-viewer"
      aria-labelledby="proof-packet-heading"
      data-testid="proof-packet-viewer"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.2 }}
    >
      <div className="panel__header">
        <h2 id="proof-packet-heading">Audit Packet</h2>
        <div className="button-row">
          <button
            className="ghost-button right-card__toggle"
            type="button"
            data-testid="download-proof-pdf"
            onClick={() => downloadProofPacketPdf(state)}
          >
            Download Proof Packet (PDF)
          </button>
          <button className="ghost-button right-card__toggle" type="button" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide details" : "Show details"}
          </button>
        </div>
      </div>
      <div className="proof-packet-viewer__summary">
        <div className="right-card__mono-block">
          <span className="kv-label">Chain hash</span>
          <span className="mono-value" data-testid="proof-chain-hash">
            {state.proof.chainHash}
          </span>
        </div>
        <div className="proof-packet-viewer__summary-grid">
          <div>
            <span className="kv-label">Decision mark</span>
            <span className="mono-value">{state.decision?.value ?? "Pending"}</span>
          </div>
          <div>
            <span className="kv-label">Packet head</span>
            <span className="mono-value">{shortHash(state.proof.chainHash, 12, 8)}</span>
          </div>
        </div>
      </div>
      {open ? (
        <div className="proof-packet-viewer__payload">
          {packetRows.map((row) => (
            <div key={row.label} className="proof-packet-viewer__row">
              <span className="kv-label">{row.label}</span>
              <span className="mono-value">{row.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </motion.section>
  );
}

export default ProofPacketViewer;
