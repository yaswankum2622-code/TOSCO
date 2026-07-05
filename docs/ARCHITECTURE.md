# TOSCO Architecture

**Trusted Orchestration & Settlement Clearance Operator**

> Agents propose. TOSCO clears. Execution obeys. Audit proves.

---

## Design Principle

TOSCO separates **extraction** from **authority**.

| Role | Responsibility |
|------|----------------|
| Reference AP Agent | Proposes payment intent — never executes |
| Vultr Serverless Inference | Extracts structured fields from documents |
| TOSCO Gate Engine | Deterministically evaluates evidence, policy, risk, and reality |
| Decision Engine | Emits ALLOW · BLOCK · FREEZE |
| Proof Packet + Ledger | Tamper-evident audit record |
| Clearance Token | HMAC-signed execution mandate (ALLOW only) |
| Mock Bank | Enforces token before simulated payment |

**The model extracts. Deterministic gates decide. Every decision becomes a verifiable Proof Packet.**

---

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND — Clearance Terminal (React / Vite / TypeScript)          │
│  ┌──────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │ Intake       │  │ Clearance Bus        │  │ Outcome           │  │
│  │ · Scenarios  │  │ · Clearance Spine    │  │ · Decision        │  │
│  │ · Proposal   │  │ · Event Log (SSE)    │  │ · Token           │  │
│  │ · Vultr link │  │ · Naive agent strip  │  │ · Mock Bank       │  │
│  │ · Custom run │  │                      │  │ · Proof / Verify  │  │
│  └──────────────┘  └──────────────────────┘  └───────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST + SSE
┌───────────────────────────────▼─────────────────────────────────────┐
│  BACKEND — FastAPI (Python / Pydantic v2)                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Orchestrator — run lifecycle, event emission, SSE bus         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Workflow-Agnostic Clearance Engine                              │  │
│  │ · WorkflowDefinition loader (YAML)                            │  │
│  │ · EvidenceProvider (seeded demo docs)                         │  │
│  │ · ExtractionSandbox → Vultr Serverless Inference              │  │
│  │ · GateEngine (G1–G6 plugins)                                  │  │
│  │ · ToolProvider (simulated enterprise signals)                 │  │
│  │ · DecisionEngine · ProofPacket · SHA-256 Ledger               │  │
│  │ · ClearanceTokenService (HMAC) · MockBankAdapter              │  │
│  │ · Human Review gate (high-value runs)                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Pipeline

```text
Reference AP Agent
   ↓ proposes payment (ActionIntent)
Scenario Evidence / Vultr Extraction Adapter
   ↓ sealed structured extraction
TOSCO Gate Engine
   ↓ six deterministic gates (G1–G6)
Decision Engine
   ↓ ALLOW · BLOCK · FREEZE
ProofPacket + SHA-256 Ledger
   ↓ tamper-evident chain
HMAC Clearance Token
   ↓ issued only on ALLOW
Mock Bank Enforcement
   ↓ token-bound execution attempt
Clearance Terminal UI
   ↓ event-driven display (no frontend verdict logic)
```

### Station sequence

| Station | Purpose |
|---------|---------|
| **PROPOSE** | Agent intent captured; no execution authority |
| **RETRIEVE** | Evidence bundle loaded (invoice, PO, GRN, vendor master, policy) |
| **EXTRACT** | Vultr or local fallback → schema-validated fields |
| **TOOLS** | Simulated policy, risk, domain-age, duplicate-invoice signals |
| **G1 Evidence** | Required documents present |
| **G2 Groundedness** | Extracted fields trace to source spans |
| **G3 Policy** | Business rules (amount limits, approval paths) |
| **G4 Risk** | Composite risk scoring |
| **G5 Reality** | External reality vs. document claims (bank account mismatch) |
| **G6 Decision Seal** | Final deterministic fold |
| **REVIEW** | Optional human gate on high-value runs |
| **TOKEN** | HMAC clearance token (ALLOW only) |
| **BANK** | Mock Bank accepts or rejects execution |
| **PROOF** | Proof Packet sealed into SHA-256 ledger |

---

## Backend Layers

### API (`app/api/`)

| Module | Role |
|--------|------|
| `app.py` | FastAPI factory, CORS, lifespan |
| `routes.py` | REST endpoints — runs, proof, verify, tamper-demo, reset |
| `sse_bus.py` | Server-sent events for live timeline |
| `schemas.py` | Request/response contracts |
| `state.py` | In-memory demo run store |

### Orchestrator (`app/orchestrator/`)

Drives the run lifecycle: loads workflow YAML, coordinates evidence → extraction → tools → gates → decision → token → proof → bank events. Emits a typed event stream consumed by the frontend over SSE.

### Clearance Engine (`app/engine/`)

Pure, deterministic Python. No LLM verdict logic inside gates.

| Component | File | Role |
|-----------|------|------|
| Gate Engine | `gate_engine.py` | Plugin registry, sequential gate execution |
| Gates G1–G6 | `gates/g1_evidence.py` … `g6_decision_seal.py` | Deterministic checks |
| Decision | `decision.py` | ALLOW / BLOCK / FREEZE fold |
| Proof | `proof.py` | Proof Packet construction |
| Ledger | `ledger.py` | SHA-256 hash chain |
| Token | `token.py` | HMAC-SHA256 clearance token |
| Mock Bank | `mock_bank.py` | Token verification + execution result |
| Review | `review.py` | Human review gate for high-value runs |

### Integrations (`app/integrations/`)

| Module | Role |
|--------|------|
| `vultr.py` | Vultr Serverless Inference client — `/v1/chat/completions`, structured JSON extraction, TLS-safe, local fallback |

Vultr **extracts only**. It does not approve, block, or move money.

### Workflows (`backend/workflows/`)

YAML `WorkflowDefinition` declares evidence types, extraction schema, gate list, tools, decision policy, and execution adapter. New workflow = new YAML + gate plugins; core engine unchanged.

---

## Frontend Architecture

Single-page React app. **No component computes a verdict** — all UI state is driven by backend events.

| Pattern | Implementation |
|---------|----------------|
| Event source | SSE (`/api/runs/{id}/events`) with REST fallback |
| State | `run/store.tsx` — folds events into clearance spine stations |
| Spine | Visual pipeline — PROPOSE through PROOF |
| Outcome rail | Decision, token, mock bank, counterfactual |
| Audit drawer | Proof seal, packet viewer, hash verifier, tamper demo |

Gate nodes flip on `GATE_COMPLETED`. Token card renders after `TOKEN_ISSUED`. Bank card after `EXECUTION_ATTEMPTED`.

---

## Event Stream

```text
PLAN_STARTED
  → EVIDENCE_RETRIEVED
  → EXTRACTION_STARTED / VULTR_EXTRACTION_*
  → EXTRACTION_SEALED
  → TOOL_CALLED
  → GATE_STARTED / GATE_COMPLETED
  → DECISION_MADE
  → TOKEN_ISSUED | CLEARANCE_TOKEN_SKIPPED
  → PROOF_SEALED
  → EXECUTION_ATTEMPTED
```

Each event: `{ event, run_id, ts, data }` — streamed live to the Clearance Terminal.

---

## Cryptographic Contracts

### SHA-256 Ledger

```text
chain_hash = sha256(prev_chain_hash + payload_hash)
```

Any edit to a sealed payload breaks every subsequent link. `verify()` walks the chain and recomputes hashes.

### Clearance Token (HMAC-SHA256)

Signed over `{ run_id, vendor_id, amount, decision, ledger_head, exp }`.

- Issued **only** for ALLOW
- Verified by Mock Bank with `hmac.compare_digest`
- Rejected on: missing token, tamper, expiry, vendor mismatch, amount mismatch, ledger head mismatch

### Proof Packet

Structured JSON from real run data: intent, workflow, evidence hashes, sealed extraction, tool results, gate outcomes, decision, reason codes, `payload_hash`, `prev_hash`, `chain_hash`, verification status, `sealed_at`.

---

## Fallback Mode

When `VULTR_API_KEY` is unset or Vultr is unreachable:

- Local extraction path activates
- `fallback_mode=true` in events
- UI shows **LIVE FALLBACK** pill
- All deterministic gates unchanged — same clearance logic, honest labeling

---

## What Is Real vs Sandbox

| Real in this build | Sandbox / simulated |
|--------------------|---------------------|
| Vultr Serverless Inference extraction | Seeded demo documents |
| Deterministic gate engine | External enterprise APIs |
| HMAC clearance token | Real payment rails |
| Mock Bank token enforcement | Production auth / RBAC |
| SHA-256 proof chain + tamper verify | Persistent database |
| SSE live event stream | Real money movement |

---

## Repository Map

```text
backend/
  app/api/          REST + SSE
  app/engine/       Gates, decision, proof, ledger, token, mock bank
  app/integrations/ Vultr adapter
  app/orchestrator/ Run lifecycle
  workflows/        YAML workflow definitions
  tests/            204 pytest cases
frontend/
  src/run/          Event-driven store
  src/components/   Clearance Terminal UI
docs/
  ARCHITECTURE.md   ← this document
  SECURITY_NOTES.md Threat model and controls
  LIVE_VULTR_PROOF.md Live inference verification
```

---

## Related Documents

- [`SECURITY_NOTES.md`](SECURITY_NOTES.md) — threat model and security controls
- [`LIVE_VULTR_PROOF.md`](LIVE_VULTR_PROOF.md) — live Vultr inference verification
