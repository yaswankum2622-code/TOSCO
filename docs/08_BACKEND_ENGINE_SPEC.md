# 08 — Backend Engine Spec

## Modules (`backend/app/`)
```
main.py            FastAPI app + routes
orchestrator.py    run lifecycle, event emission
models.py          ActionIntent, RunContext, SealedExtraction, GateResult, enums
engine/
  workflow.py      WorkflowDefinition loader (YAML → validated model)
  evidence.py      EvidenceProvider (VultronRetriever + local fallback)
  extraction.py    ExtractionSandbox (Vultr Serverless Inference + fallback; seals output)
  gate_engine.py   registry + runner
  gates/g1..g5.py  gate plugins
  tools.py         ToolProvider interfaces (+ simulated impls)
  decision.py      DecisionEngine (severity fold)
  ledger.py        ProofPacket + HashLedger
features/
  clearance_token.py  issue/verify HMAC token
  counterfactual.py   Observe Mode
  evidence_locker.py  locker assembly
  auditor.py          auditor view/text
  sentinel.py         local attack memory
  mock_bank.py        execution adapter (wraps clearance_token.mock_bank_execute)
  ref_agent.py        Reference AP Agent
events.py          Event enum + async SSE bus
db.py              SQLite schema + repository
```

## Data models
`Decision{ALLOW,ESCALATE,BLOCK,REQUEST_MORE_EVIDENCE,FREEZE,SIMULATE_ONLY}` · `GateStatus{PASS,WARN,FAIL}` · `ActionIntent` · `ProposedAction` · `SealedExtraction(frozen; fields, source_spans, extractor, sealed_hash())` · `GateResult(gate_id,status,decision,reason_code,human_reason,evidence_refs)` · `ToolCall(tool_id,input,output,simulated)` · `RunContext(run_id,intent,workflow_id,extraction,evidence,signals,tool_calls,results,fallback_mode)`.

## SQLite schema
```sql
runs(run_id PK, workflow_id, scenario, intent_json, decision, fallback_mode, created_at)
evidence(run_id, evidence_type, doc_id, content_json)
extractions(run_id PK, fields_json, spans_json, extractor, sealed_hash)
tool_calls(run_id, tool_id, input_json, output_json, simulated)
gate_results(run_id, gate_id, status, decision, reason_code, human_reason, ordinal)
ledger(seq PK AUTOINCREMENT, run_id, payload_hash, prev_hash, chain_hash, packet_json, sealed_at)
tokens(run_id, token, decision, exp, ledger_head)
sentinel(id PK, run_id, workflow, vendor_id, amount, decision, reason_codes_json, failed_signals_json, recorded_at)
events(run_id, event, data_json, ts)
```

## Event model
Emit in order: `PLAN_STARTED, EVIDENCE_RETRIEVED(×passes), EXTRACTION_STARTED, EXTRACTION_SEALED, TOOL_CALLED(×tools), GATE_STARTED/GATE_COMPLETED(×gates), DECISION_MADE, TOKEN_ISSUED(if ALLOW), PROOF_SEALED, EXECUTION_ATTEMPTED(on bank call)`.

## Orchestrator lifecycle
`start(scenario)`: create run → load WorkflowDefinition → EvidenceProvider.retrieve (emit per pass) → ExtractionSandbox.extract+seal → ToolProvider calls (emit each) → GateEngine.run (emit per gate) → DecisionEngine.fold → if ALLOW: ClearanceTokenService.issue → seal ProofPacket + ledger → Sentinel.observe → persist. All state written to SQLite; events streamed.

## Component specs
- **EvidenceProvider:** returns docs for `required_evidence_types`; VultronRetriever primary, local seed fallback (`fallback_mode=true`).
- **ExtractionSandbox:** calls Vultr Serverless Inference; validates against `extraction_schema.required_fields`; returns `SealedExtraction` (immutable). Injected instructions land in non-decision fields and are ignored by gates.
- **ToolProviders:** `policy_tool, risk_tool, bank_owner_check, domain_age_check, logistics_check` — real interface `call(ctx)->output`, simulated bodies now.
- **GateEngine:** runs `wf.gates_to_run` via `REGISTRY`; each gate pure.
- **DecisionEngine:** severity fold; ALLOW only if all pass; owner-mismatch → FREEZE.
- **ProofPacket + HashLedger:** seal + SHA-256 chain + verify.
- **ClearanceTokenService:** HMAC-SHA256 over `{run_id,vendor_id,amount,decision,ledger_head,exp}`, ALLOW only.
- **MockBankAdapter:** verify token → execute/reject.
- **Reference AP Agent:** builds an ActionIntent per scenario and POSTs `/agent/propose` → `/runs/start`.
- **Sentinel:** record BLOCK/FREEZE patterns locally.

## Deterministic invariants (must hold)
1. No gate branches on raw model text; gates read sealed fields + typed signals.
2. Extraction sealed at first run; replay uses sealed values, never re-extracts.
3. Same seed → same gate results → same decision → same reason codes.
4. ALLOW ⇒ token issued; non-ALLOW ⇒ no token.
5. Any ledger edit ⇒ `verify()` false.
