# 04 — Architecture

## Layered
```
┌ FRONTEND — Clearance Terminal (React Vite) ───────────────────────┐
│  left: ScenarioSwitcher · ReferenceAPAgentCard · ActionIntentPanel │
│        · DocumentPreview                                           │
│  center: LiveTimeline · EvidencePassCard · ToolCallLog · GateChain │
│          · NaiveAgentStrip                                         │
│  right: DecisionCard · ClearanceTokenCard · MockBankExecutionCard  │
│         · ProofSeal · ProofPacketViewer · HashVerifier             │
│         · SentinelMemoryCard · ObserveModeCounterfactual           │
│  SandboxBadge (fixed) · TamperDemoButton                          │
└─────────────┬─────────────────────────────────────────────────────┘
              │ REST + SSE
┌─────────────▼─────────────────────────────────────────────────────┐
│ BACKEND — FastAPI                                                  │
│  Orchestrator (run lifecycle + event emission)                    │
│  ┌ WORKFLOW-AGNOSTIC CLEARANCE ENGINE ──────────────────────────┐ │
│  │ WorkflowDefinition loader · EvidenceProvider ·               │ │
│  │ ExtractionSandbox(Vultr) · GateEngine(plugins) ·             │ │
│  │ ToolProvider · DecisionEngine · ProofPacket · HashLedger ·   │ │
│  │ ClearanceTokenService · MockBankAdapter · Sentinel           │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  SQLite (WAL)                                                      │
└───────────────────────────────────────────────────────────────────┘
```

## Frontend architecture
Single-page React (Vite). State per run driven **only** by backend events over SSE (fallback: 500ms poll of `/api/runs/{id}`). No component computes a verdict. A gate node flips only on `GATE_COMPLETED`; the token card renders only after `TOKEN_ISSUED`; the bank card renders only after `EXECUTION_ATTEMPTED`. `api.js` centralizes fetch/SSE.

## Backend architecture
FastAPI + async orchestrator. The engine is pure and deterministic; only EvidenceProvider and ExtractionSandbox perform I/O (Vultr, with local fallback). Repository pattern over SQLite (no raw SQL in engine logic).

## Workflow-agnostic engine + plugin model
`WorkflowDefinition` (YAML) declares evidence types, extraction schema, gate list, tools, decision policy, proof template, execution adapter. Gates are plugins registered by id (`@gate("G3_POLICY")`). The engine runs `wf.gates_to_run` via the registry. New workflow = new YAML + new plugins; core untouched.

## Event stream
`PLAN_STARTED → EVIDENCE_RETRIEVED → EXTRACTION_STARTED → EXTRACTION_SEALED → TOOL_CALLED → GATE_STARTED → GATE_COMPLETED → DECISION_MADE → TOKEN_ISSUED → PROOF_SEALED → EXECUTION_ATTEMPTED`. Each: `{event, run_id, ts, data}`.

## Hash ledger
SHA-256 chain: `chain_hash = sha256(prev_chain_hash + payload_hash)`. Any edit breaks every later link. `verify()` walks the chain and recomputes payload hashes.

## Proof Packet
Structured JSON built from real run data: intent, workflow_id, evidence used, sealed extraction, tool calls, gate results, decision, reason codes, payload_hash, prev_hash, chain_hash, verification status, sealed_at. Embeds the Evidence Locker.

## Clearance Token
HMAC-SHA256 over `{run_id, vendor_id, amount, decision, ledger_head, exp}`. Issued only for ALLOW. Verified by the Mock Bank.

## Mock Bank
Pure verifier. Accepts only a valid, unexpired, untampered ALLOW token bound to the requested vendor/amount and current ledger head. All else rejected.

## Fallback mode
If Vultr Serverless Inference or VultronRetriever is unavailable, the engine uses local extraction/retrieval and sets `fallback_mode=true`; the UI shows a SANDBOX/FALLBACK label. Determinism and all gates still hold.

## Vultr integration points
- **ExtractionSandbox** → Vultr Serverless Inference (extract fields from invoice text; produce plain-language explanations).
- **EvidenceProvider** → VultronRetriever (multi-pass retrieval of evidence docs).
Both visible in ToolCallLog with latency.
