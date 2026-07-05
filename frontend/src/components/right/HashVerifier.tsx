import { motion, useReducedMotion } from "framer-motion";

import type { RunStoreState } from "../../run/store";
import { yesNo } from "../../utils/format";

interface HashVerifierProps {
  state: RunStoreState;
  onVerify: () => void;
  onTamper: () => void;
  onReset: () => void;
  loading: boolean;
}

function HashVerifier({ state, onVerify, onTamper, onReset, loading }: HashVerifierProps) {
  const shouldReduceMotion = useReducedMotion();

  if (state.proof?.sealed !== true || state.proof.chainHash === null || state.runId === null) {
    return null;
  }

  const verification = state.verification;
  const tone = verification ? (verification.verified ? "allow" : "deny") : "mute";
  const disabled = loading || state.runId === null;

  return (
    <motion.section
      key={`${state.runId}-${verification?.verified ?? "unchecked"}-${verification?.tamperedField ?? "none"}`}
      className={`panel right-card hash-verifier ${verification ? `right-card--${tone}` : ""}`}
      aria-labelledby="hash-verifier-heading"
      data-testid="hash-verifier"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2, ease: "easeOut" }}
    >
      <div className="panel__header">
        <h2 id="hash-verifier-heading">Hash Verifier</h2>
        <span
          className={`status-pill ${
            verification ? (verification.verified ? "status-pill--allow" : "status-pill--deny") : "status-pill--warning"
          }`}
          data-testid="hash-verifier-status"
        >
          {verification ? (verification.verified ? "VERIFIED" : "FAILED") : "Awaiting check"}
        </span>
      </div>
      <p className="hash-verifier__caption">
        SHA-256 hash chain — each record&apos;s hash includes the previous. Any edit breaks every later link.
      </p>
      <div className="right-card__mono-block">
        <span className="kv-label">Chain head</span>
        <span className="mono-value" data-testid="hash-verifier-chain-head">
          {verification?.chainHead ?? state.proof.chainHash}
        </span>
      </div>
      {verification ? (
        <div className="hash-verifier__grid">
          <div className="right-card__mono-block">
            <span className="kv-label">Result</span>
            <span className={`mono-value hash-verifier__result hash-verifier__result--${tone}`} data-testid="hash-verifier-result">
              {verification.verified ? "VERIFIED" : "FAILED"}
            </span>
          </div>
          <div className="right-card__mono-block">
            <span className="kv-label">Ledger chain</span>
            <span className="mono-value">{yesNo(verification.ledgerChainValid)}</span>
          </div>
          <div className="right-card__mono-block">
            <span className="kv-label">Packet entry</span>
            <span className="mono-value">{yesNo(verification.packetEntryValid)}</span>
          </div>
          {verification.tamperedField ? (
            <div className="right-card__mono-block">
              <span className="kv-label">Tampered field</span>
              <span className="mono-value" data-testid="hash-verifier-tampered-field">
                {verification.tamperedField}
              </span>
            </div>
          ) : null}
          {verification.brokenRecordIndex !== null && !verification.verified ? (
            <div className="right-card__mono-block hash-verifier__broken">
              <span className="kv-label">Chain break</span>
              <span className="mono-value" data-testid="hash-verifier-broken-record">
                chain broken at record {verification.brokenRecordIndex}
              </span>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="empty-state">Verify the sealed chain to confirm the ledger is still intact.</p>
      )}
      <div className="hash-verifier__actions">
        <button className="ghost-button right-card__action" type="button" onClick={onVerify} disabled={disabled}>
          Verify chain
        </button>
        <button className="ghost-button right-card__action" type="button" onClick={onTamper} disabled={disabled}>
          Tamper a row
        </button>
        <button className="ghost-button right-card__action" type="button" onClick={onReset} disabled={loading}>
          Reset
        </button>
      </div>
    </motion.section>
  );
}

export default HashVerifier;
