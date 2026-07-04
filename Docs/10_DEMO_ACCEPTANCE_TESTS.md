# 10 — Demo Acceptance Tests

Each test = precondition → action → expected. These are the definition of done. (Backend gate/feature logic already verified by pytest; these cover the full demo path.)

| # | Test | Action | Expected |
|---|---|---|---|
| 1 | Clean → ALLOW | start `clean` | decision ALLOW; all 5 gates PASS |
| 2 | Clean → token issued | after #1 | `TOKEN_ISSUED`; ClearanceTokenCard shows token+exp |
| 3 | Clean → bank accepts | `/execution/attempt` valid token | `executed:true, reason:CLEARED` |
| 4 | Poisoned → naive approves | injection scenario | NaiveAgentStrip shows APPROVED (attacker acct) |
| 5 | Poisoned → TOSCO BLOCKS | start `injection` | TOSCO detects injected payment-routing / bank mismatch / suspicious instruction; decision BLOCK; the responsible gate FAILs |
| 6 | Poisoned → no ALLOW token | after #5 | no valid ALLOW token is issued |
| 7 | Poisoned → bank rejects | `/execution/attempt` token=null | `executed:false, NO_TOKEN` |
| 8 | Forgery → doc gates pass | start `forgery` | G1, G2 PASS |
| 9 | Forgery → Reality Gate fails | same run | G5 FAIL, reason REALITY_OWNER_MISMATCH |
| 10 | Forgery → FREEZE | same run | decision FREEZE |
| 11 | Forgery → bank rejects | `/execution/attempt` token=null | `executed:false, NO_TOKEN` |
| 12 | Proof verify passes | `/verify` after any seal | `verified:true` |
| 13 | Tamper verify fails | `/tamper-demo` then `/verify` | `verified:false` |
| 14 | No-token execution rejects | `/execution/attempt` token=null on clean | `executed:false, NO_TOKEN` |
| 15 | Tampered token rejects | edit token bytes | `executed:false, TAMPERED_TOKEN` |
| 16 | Amount mismatch rejects | valid token, wrong amount | `executed:false, AMOUNT_MISMATCH` |
| 17 | Vendor mismatch rejects | valid token, wrong vendor | `executed:false, VENDOR_MISMATCH` |
| 18 | Frontend verdicts from backend only | inspect network | every verdict/gate flip maps to a backend event; none client-computed |
| 19 | Workflow loads from YAML | GET `/workflows/vendor_payment` | returns parsed YAML definition |
| 20 | Fallback labeled | force Vultr off | `fallback_mode:true`; UI shows SANDBOX/FALLBACK badge |

Extra (optional): expired token → `EXPIRED_TOKEN`; ledger mismatch → `LEDGER_MISMATCH`.

Acceptance bar: tests 1–20 pass, and the 60-second recording plays the clean→injection→forgery→proof arc twice without stutter.
