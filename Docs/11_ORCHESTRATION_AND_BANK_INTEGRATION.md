# 11 — Orchestration & Bank Integration

## How we prove TOSCO works in orchestration
The demo is a real multi-agent orchestration, not a form:

1. **Reference AP Agent** builds an `ActionIntent` for the chosen scenario and calls `POST /api/agent/propose`, then `POST /api/runs/start`. It is a genuine agent step — the proposer is separate from the clearer.
2. **TOSCO** runs the pipeline (plan → retrieve → extract → tools → gates → decide) and emits events.
3. **Clearance Token** is generated ONLY for ALLOW, bound to vendor+amount+ledger head.
4. **Mock Bank** (`POST /api/execution/attempt`) accepts or rejects purely on token validity.
5. **Bypass attempt** (token=null) → `NO_TOKEN`, rejected. Proves the agent cannot skip clearance.
6. **Blocked/frozen** decision → no token → bank rejects. Proves a bad decision cannot execute.

## The control property, demonstrated
- ALLOW + valid token → **executed**.
- BLOCK/FREEZE → no token → **rejected**.
- Tampered/expired/mismatched token → **rejected**.
"Execution blocked before money moved" appears on every attack path.

## Production version (contract, not built)
The Mock Bank is a stand-in for the execution boundary of real systems. In production:
- The **payment rail / bank** requires a TOSCO-signed clearance (token → signed mandate) before releasing funds.
- The **ERP / AP suite** calls `/agent/propose` before posting a payment run; TOSCO returns clear/block.
- **Treasury** gates high-value releases on external-signal confirmation.
Interface is identical (ActionIntent in, token out); only adapters differ. `execution_adapter: sandbox` → `execution_adapter: <bank_connector>`.

## Contract for real financial services (future)
- Signed clearance attestation per action (JWS/HMAC → mTLS).
- One-time redemption (nonce) at the rail.
- Proof Packet retained as the audit workpaper for the release.
- Deployment self-hosted in the customer VPC ("your data never leaves").

## Why this is enough for a 24-hour sandbox demo
It proves the entire loop — propose, clear, sign, enforce, prove — end to end with zero real-money risk. A pre-production buyer evaluates the control architecture, which is exactly what is shown. Real connectors are a Phase-3 integration, not a hackathon requirement.
