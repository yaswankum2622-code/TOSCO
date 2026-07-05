# 05 — API Contract (frozen)

All JSON. Base: `/api`. Errors: `{error_code, message}` with appropriate HTTP status. Verdicts NEVER come from the client.

### GET /api/health
Purpose: liveness + fallback state.
Response: `{ "status": "ok", "fallback_mode": false }`

### GET /api/workflows
Purpose: list loadable workflows.
Response: `[{ "workflow_id": "vendor_payment", "workflow_name": "AI Vendor Payment & Bank-Change Clearance" }]`

### GET /api/workflows/{workflow_id}
Purpose: full WorkflowDefinition (from YAML).
Response: the parsed definition (see doc 06). 404 `WORKFLOW_NOT_FOUND`.

### POST /api/agent/propose
Purpose: Reference AP Agent submits an ActionIntent; returns intent echo + a `run` handle. Does not decide.
Request:
```json
{ "agent_id":"ap-agent-01","workflow":"vendor_payment",
  "action":{"type":"payment","vendor_id":"V-1042","amount":340000,"currency":"USD","bank_account_last4":"8821"},
  "evidence_refs":["invoice-2291"],"declared_confidence":0.94,"requested_mode":"assisted",
  "scenario":"clean" }
```
Response: `{ "intent_id":"...", "accepted":true }`. Errors: 422 `INVALID_INTENT`.

### POST /api/runs/start
Purpose: start a real clearance run for a scenario (clean | injection | forgery). Seeds evidence only; the engine runs the full pipeline.
Request: `{ "scenario":"forgery" }`
Response: `{ "run_id":"..." }`

### GET /api/runs/{run_id}
Purpose: full RunContext snapshot (intent, evidence refs, extraction hash, tool_calls, gate_results, decision, fallback_mode).
Errors: 404 `RUN_NOT_FOUND`.

### GET /api/runs/{run_id}/events
Purpose: **SSE** stream of run events (doc 04 event list). Content-Type `text/event-stream`. Each message `data: {event,run_id,ts,data}`.

### GET /api/runs/{run_id}/proof
Purpose: sealed Proof Packet (after PROOF_SEALED). Includes Evidence Locker + auditor view.
Errors: 409 `PROOF_NOT_READY`, 404 `RUN_NOT_FOUND`.

### GET /api/runs/{run_id}/verify
Purpose: recompute + walk the hash chain live.
Response: `{ "verified": true, "chain_head":"..." }`

### POST /api/runs/{run_id}/tamper-demo
Purpose: mutate one ledger row to prove tamper-evidence.
Response: `{ "tampered_field":"amount", "verify_now": false }`

### POST /api/execution/attempt
Purpose: Mock Bank execution. Accepts only a valid ALLOW token bound to this run/vendor/amount/ledger head.
Request: `{ "run_id":"...", "token":"<jwt-like>|null", "vendor_id":"V-1042", "amount":340000 }`
Response (accept): `{ "executed":true, "reason":"CLEARED", "amount":340000 }`
Response (reject): `{ "executed":false, "reason":"NO_TOKEN|NON_ALLOW_TOKEN|EXPIRED_TOKEN|TAMPERED_TOKEN|VENDOR_MISMATCH|AMOUNT_MISMATCH|LEDGER_MISMATCH|MALFORMED_TOKEN" }`

### POST /api/reset
Purpose: wipe runs/ledger and reseed. Must complete <30s.
Response: `{ "reset": true }`

## Demo behavior notes
- `runs/start` with `scenario=injection`: the NaiveAgentStrip shows the naive agent APPROVING the attacker payment; TOSCO detects the injected payment-routing / bank mismatch / suspicious instruction and returns **BLOCK**; no ALLOW token is issued; `/execution/attempt` returns `NO_TOKEN`.
- `scenario=forgery` → FREEZE, no token, `/execution/attempt` returns `NO_TOKEN`.
- All timing-sensitive UI transitions are driven by `/events`, never by client timers beyond the poll fallback.
