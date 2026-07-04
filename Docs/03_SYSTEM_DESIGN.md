# 03 — System Design

## End-to-end flow (demo)
```
Reference AP Agent
   │  POST /api/agent/propose  (ActionIntent)
   ▼
TOSCO Clearance Engine
   plan → retrieve(×5) → extract(Vultr, sealed) → tools → gates → decision
   │
   ├─ ALLOW  → issue Clearance Token (HMAC-SHA256, bound to vendor+amount+ledger head)
   ├─ ESCALATE → human review card (no token)
   └─ BLOCK / FREEZE → no token + Sentinel records pattern
   │
   ▼  seal Proof Packet → hash ledger
Mock Bank / Payment Rail
   POST /api/execution/attempt  (token + vendor + amount)
   accepts ONLY a valid, unexpired, untampered ALLOW token bound to this run
   else → REJECTED (NO_TOKEN / NON_ALLOW / EXPIRED / TAMPERED / VENDOR_MISMATCH /
                    AMOUNT_MISMATCH / LEDGER_MISMATCH)
   ▼
Execution Result  → "Execution blocked before money moved" (attack cases)
```

## Why "no valid token → no execution"
The bank rail does not trust the agent, the network, or TOSCO's word — it trusts a cryptographic signature over the exact cleared action. A BLOCK/FREEZE produces no token; a stolen or edited token fails the HMAC check; a token for a different vendor/amount/ledger state is rejected. Enforcement is mechanical, not procedural.

## Production integration (not built now)
The Mock Bank is the seam where, in production, TOSCO sits at the **execution boundary** of real rails and systems:
- **Banks / payment rails:** the rail requires a TOSCO-signed clearance before releasing a wire (token → mandate).
- **ERPs (SAP, Oracle, Workday):** AP module calls `/agent/propose` before posting a payment run.
- **AP automation (Tipalti, Ramp, Medius):** agent actions route through TOSCO pre-release.
- **Treasury systems:** high-value releases gated on external-signal confirmation.
Same ActionIntent envelope, same token contract; only the adapters change. The `execution_adapter` field in the WorkflowDefinition selects `sandbox` now, a real connector later.

## Why sandbox is enough for 24h
A pre-production enterprise buyer evaluates the *architecture and the control*, not a production logo. The sandbox proves the full control loop — propose, clear, sign, enforce, prove — with zero real-money risk. Every screen is labeled SANDBOX.
