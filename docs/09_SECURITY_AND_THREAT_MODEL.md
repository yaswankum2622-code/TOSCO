# 09 — Security & Threat Model

For each threat: the attack, TOSCO's mitigation, what's simulated, and production hardening.

## 1. Prompt injection (poisoned invoice/email)
Attack: hidden text in a document instructs the agent to approve/redirect payment to an attacker account.
Mitigation: the LLM only extracts; output is schema-validated and sealed; gates read structured fields, never model text. The injected payment-routing / bank mismatch is caught deterministically — the proposed account does not match the verified vendor master (groundedness + policy), and a suspicious-instruction signal flags it — so TOSCO returns **BLOCK**. No ALLOW token is issued; the Mock Bank rejects execution.
Demo: naive agent APPROVES the attacker payment; TOSCO detects the injected mismatch and BLOCKS; no token; bank rejects.
Simulated: the extraction model (Vultr) + a seeded poisoned field.
Production: extraction sandbox isolation, output allow-listing, adversarial eval of extractor.

## 2. Forged document chain (perfect internal consistency)
Attack: matching invoice + PO + GRN + bank-change letter — every internal check passes.
Mitigation: Reality Gate checks external signals a forger doesn't control (bank-owner match, domain age, logistics). Internal consistency alone caps at ESCALATE; high-value needs external confirmation. Owner mismatch → FREEZE.
Simulated: external-signal provider behind a pluggable interface.
Production: real bank-verification (Eftsure-class), registry (KYB), logistics APIs.

## 3. Bank-change fraud (BEC)
Attack: fraudulent vendor bank-detail change → wire diverted.
Mitigation: recent-change risk signal + first-payment-to-new-account policy + Reality Gate owner check. In the bank-change workflow, an out-of-band confirmation is mandatory.
Production: enforced out-of-band verification + change-history diff in the Proof Packet.

## 4. Agent bypass (skip TOSCO, call the rail directly)
Attack: compromised agent calls the payment rail without clearance.
Mitigation: the rail requires a valid TOSCO-signed Clearance Token; no token → no execution. Demo: `/execution/attempt` with `token=null` → `NO_TOKEN`.
Production: TOSCO signs the mandate the rail requires; rail rejects unsigned releases.

## 5. Tampered proof (edit the record after the fact)
Attack: alter a sealed decision or amount.
Mitigation: SHA-256 hash chain; any edit breaks every later link; live `verify()`. Demo: `/tamper-demo` → verify fails.
Production: periodic external anchoring of the chain head (publish digests).

## 6. Malicious plugin (rogue gate/workflow)
Attack: a workflow plugin tries to force ALLOW or touch the ledger.
Mitigation: plugins declare; core decides. Gates return `GateResult` only; they cannot write the ledger, mutate other plugins, or issue tokens.
Production: signed policy packs, plugin sandboxing, review gate for new workflows.

## 7. Clearance token theft / tamper / replay
Attack: steal, edit, or reuse a token.
Mitigation: HMAC-SHA256 signature (tamper → reject); bound to vendor+amount+ledger_head (mismatch → reject); short expiry (replay window minimized); non-ALLOW → no token.
Production: KMS/HSM-held key + rotation, nonce/one-time redemption, mTLS to the rail.

## What is simulated (labeled SANDBOX)
Extraction model may fall back to local; external signals; the bank rail; all data. No real money, no real bank/ERP.

## What production hardening needs
KMS-held signing keys; real external-signal vendors; execution attestation from real rails; RBAC + SSO/SCIM; append-only ledger with external anchor; SOC 2; threat-model review of the extractor.
