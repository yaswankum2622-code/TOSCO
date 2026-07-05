import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../run/store";
import { shortHash } from "../utils/format";

interface ProofSealProps {
  state: RunStoreState;
}

function GuillocheSeal() {
  return (
    <svg
      className="proof-seal__guilloche"
      viewBox="0 0 320 320"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {Array.from({ length: 18 }, (_, index) => (
        <ellipse
          key={`seal-ring-${index}`}
          cx="160"
          cy="160"
          rx={92 + (index % 6) * 9}
          ry={48 + (index % 6) * 10}
          transform={`rotate(${index * 20} 160 160)`}
          stroke="currentColor"
          strokeOpacity={index % 2 === 0 ? 0.35 : 0.16}
          strokeWidth="1"
        />
      ))}
      {Array.from({ length: 8 }, (_, index) => (
        <circle
          key={`seal-circle-${index}`}
          cx="160"
          cy="160"
          r={38 + index * 12}
          stroke="currentColor"
          strokeOpacity={index === 0 ? 0.32 : 0.14}
          strokeWidth="1"
        />
      ))}
    </svg>
  );
}

function CrackOverlay() {
  return (
    <svg
      className="proof-seal__crack"
      viewBox="0 0 320 320"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M126 26L156 84L134 122L174 176L154 214L188 264L164 294"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d="M154 214L118 236L130 272"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d="M174 176L212 160L224 126"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ProofSeal({ state }: ProofSealProps) {
  const shouldReduceMotion = useReducedMotion();
  const isBroken = state.verification ? !state.verification.verified : false;
  const sealStatus = state.verification
    ? state.verification.verified
      ? "VERIFIED"
      : "TAMPERED"
    : "SEALED";

  return (
    <section className="panel proof-seal-card" aria-labelledby="proof-seal-heading">
      <div className="panel__header">
        <h2 id="proof-seal-heading">Proof Seal</h2>
        <span className={`status-pill ${isBroken ? "status-pill--offline" : "status-pill--online"}`}>
          {state.verification ? (state.verification.verified ? "Chain Intact" : "Chain Broken") : "Awaiting verification"}
        </span>
      </div>
      {state.proof?.sealed !== true || state.proof.chainHash === null ? (
        <div className="proof-seal proof-seal--dormant" data-testid="proof-seal">
          <div className="proof-seal__ring">
            <GuillocheSeal />
            <div className="proof-seal__inner">
              <span className="proof-seal__caption">Proof Seal</span>
              <strong className="proof-seal__status">ARMED</strong>
              <code>awaiting run</code>
              <code>ledger standby</code>
            </div>
          </div>
        </div>
      ) : (
        <motion.div
          key={`${state.proof.chainHash}-${sealStatus}`}
          className={`proof-seal ${isBroken ? "proof-seal--broken" : "proof-seal--sealed"}`}
          data-testid="proof-seal"
          initial={shouldReduceMotion ? false : { scale: 1.08, rotate: 3, opacity: 0.2 }}
          animate={{
            scale: 1,
            rotate: 0,
            opacity: 1
          }}
          transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.32, ease: "easeOut" }}
        >
          <div className="proof-seal__ring">
            <GuillocheSeal />
            {isBroken ? <CrackOverlay /> : null}
            {isBroken ? <span className="proof-seal__tampered-flag">TAMPERED</span> : null}
            <div className="proof-seal__inner">
              <span className="proof-seal__caption">Proof Sealed</span>
              <strong className="proof-seal__status">{sealStatus}</strong>
              <code>{shortHash(state.proof.chainHash, 12, 10)}</code>
              <code>{shortHash(state.verification?.chainHead ?? state.proof.chainHash, 12, 10)}</code>
            </div>
          </div>
        </motion.div>
      )}
    </section>
  );
}

export default ProofSeal;
