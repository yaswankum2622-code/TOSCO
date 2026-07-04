import { motion, useReducedMotion } from "framer-motion";

import type { RunSummaryResponse, VerifyRunResponse } from "../api/types";
import { shortHash } from "../utils/format";

interface ProofSealProps {
  run: RunSummaryResponse | null;
  verification: VerifyRunResponse | null;
}

function ProofSeal({ run, verification }: ProofSealProps) {
  const shouldReduceMotion = useReducedMotion();
  const isBroken = verification ? !verification.verified : false;

  return (
    <section className="panel proof-seal-card" aria-labelledby="proof-seal-heading">
      <div className="panel__header">
        <h2 id="proof-seal-heading">Proof Seal</h2>
        <span className={`status-pill ${isBroken ? "status-pill--offline" : "status-pill--online"}`}>
          {verification ? (verification.verified ? "Chain Intact" : "Chain Broken") : "Awaiting verification"}
        </span>
      </div>
      {!run ? (
        <p className="empty-state">The seal appears once the backend emits PROOF_SEALED.</p>
      ) : (
        <motion.div
          className={`proof-seal ${isBroken ? "proof-seal--broken" : ""}`}
          initial={shouldReduceMotion ? false : { scale: 1.06, rotate: 3, opacity: 0 }}
          animate={{ scale: 1, rotate: 0, opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          <div className="proof-seal__ring">
            <div className="proof-seal__inner">
              <span className="proof-seal__caption">PROOF SEALED</span>
              <strong className="proof-seal__status">{isBroken ? "TAMPERED" : "VERIFIED"}</strong>
              <code>{shortHash(run.proof_hash, 12, 10)}</code>
              <code>{shortHash(run.ledger_entry_hash, 12, 10)}</code>
            </div>
          </div>
        </motion.div>
      )}
    </section>
  );
}

export default ProofSeal;
