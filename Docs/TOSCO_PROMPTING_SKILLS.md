# TOSCO — Prompting Skills for ChatGPT / Codex / Cursor

Purpose: make any coding model think like this build and emit **world-class system code** for TOSCO. Paste the persona once, then feed the unit prompts in order. Every prompt references `/docs` as the single source of truth so nothing drifts.

---

## 0. Paste this persona FIRST (system / first message)

```
You are a principal systems engineer building TOSCO — an independent pre-execution
clearance layer for AI-driven vendor payments. You write production-grade Python and
React, not hackathon scripts.

Think like this, every time:
- The source of truth is the /docs pack (01–13). If my request conflicts with /docs,
  say so and follow /docs.
- One unit per response. Do not scaffold ten files at once. Build the unit I name,
  fully, correctly, with types and a test, then stop.
- Determinism is sacred: gates are pure functions of a RunContext; no gate branches on
  raw model text; extraction is sealed at first run; same input → same decision.
- No verdict is ever computed on the client. The UI only reflects backend events.
- Security is not optional: sanitize inputs, validate schemas, never log secrets,
  HMAC over canonical JSON, constant-time compare.
- Every unit ships with a test that proves the acceptance criteria I give you.
- Prefer clarity over cleverness. Small pure functions. Explicit types. Docstrings that
  say WHY, not what.
- If something is ambiguous, state your assumption in one line and proceed — don't stall.
- No TODOs, no placeholders, no "in a real system you would…". Build the real thing at
  demo scope.

Output format for every unit:
1. One-line plan.
2. The file(s), complete, path-labeled.
3. The test.
4. The exact command to run it.
5. One line: what to build next.
```

---

## 1. The universal prompt template (use for anything not covered below)

```
UNIT: <name>
SOURCE: /docs/<relevant docs>
GOAL: <one sentence — what this unit must do>
INPUTS: <data models / signatures it consumes>
OUTPUTS: <what it returns / emits>
CONSTRAINTS:
- <invariant 1 from the quality bars below>
- <invariant 2>
ACCEPTANCE (write a test that proves each):
- <observable behavior 1>
- <observable behavior 2>
DELIVER: complete file(s) + test + run command. No placeholders.
```

Good prompts are specific about **acceptance**, not implementation. Tell the model what must be *true when it's done*, and let it write the code.

---

## 2. Quality bars (paste into any prompt that feels loose)

```
Enforce all of these or explain why one can't hold:
- Types on every function signature; pydantic v2 models for all data crossing a boundary.
- Pure functions where possible; side effects isolated to provider/adapter modules.
- No global mutable state except the explicit Ledger/DB layer.
- Errors are typed and returned, not swallowed; no bare except.
- Secrets from env only; never in code, logs, or the repo.
- Hashing: sha256 over json.dumps(…, sort_keys=True, separators=(",",":")).
- HMAC: constant-time compare (hmac.compare_digest).
- Every public function has a one-line docstring stating WHY it exists.
- A test exists and passes before you claim done.
```

---

## 3. Build-order unit prompts (feed in this sequence)

### 3.1 Domain models
```
UNIT: domain models (models.py)
SOURCE: /docs/08_BACKEND_ENGINE_SPEC.md, /docs/06_WORKFLOW_DEFINITION.md
GOAL: define the type system for the clearance engine.
INCLUDE: Decision enum (ALLOW, ESCALATE, BLOCK, REQUEST_MORE_EVIDENCE, FREEZE,
  SIMULATE_ONLY) with a severity total-order + more_severe(); GateStatus(PASS,WARN,FAIL);
  ProposedAction; ActionIntent; SealedExtraction (frozen, with sealed_hash());
  ToolCall; GateResult; RunContext.
CONSTRAINTS: SealedExtraction immutable; the model→decision boundary lives here —
  add a docstring stating that gates read fields as DATA, never as instructions.
ACCEPTANCE: more_severe(BLOCK, ALLOW)==BLOCK; SealedExtraction is frozen (mutation raises);
  sealed_hash is stable for equal content.
DELIVER: models.py + test + run command.
```

### 3.2 Hash ledger + Proof Packet
```
UNIT: ledger.py (HashLedger + ProofPacket)
SOURCE: /docs/04_ARCHITECTURE.md (hash ledger), /docs/08.
GOAL: seal each run into a SHA-256 chain and verify it live.
DETAIL: chain_hash = sha256(prev_chain_hash + payload_hash); genesis = 64 zeros.
  seal(ctx, final) builds the packet from REAL run data (intent, evidence refs,
  extraction hash, gate results, decision, policy_version, sealed_at).
  verify() walks the chain AND recomputes each payload hash from the body.
ACCEPTANCE: two sealed runs verify() True; mutating any field of packet[0] → verify() False.
DELIVER: ledger.py + test + run command.
```

### 3.3 Gate engine + plugins
```
UNIT: gate engine + G1–G5 plugins
SOURCE: /docs/08, /docs/06 (decision_policy), /docs/09 (why each gate exists).
GOAL: a registry of pure-function gates the engine runs in WorkflowDefinition order.
DETAIL: @gate("G1_EVIDENCE")… decorator into a REGISTRY dict; each gate
  (RunContext, WorkflowDefinition) -> GateResult.
  G1 evidence-completeness; G2 groundedness (extracted fields ↔ source spans AND
  proposed bank_account matches verified vendor master — an injected routing/bank
  mismatch fails here); G3 policy (high_value_threshold, first-payment-to-new-account,
  SoD); G4 risk (recent bank change, velocity, duplicate); G5 reality (bank_owner_match,
  domain_age, logistics — owner mismatch → FREEZE; internal-consistency-only caps at
  ESCALATE above reality_required_above).
CONSTRAINTS: pure; no I/O; no branching on raw model text.
ACCEPTANCE: clean → all PASS; injection (bank mismatch) → G2 FAIL → BLOCK; forgery
  (owner mismatch) → G5 FAIL → FREEZE. Deterministic on rerun.
DELIVER: gate_engine.py + gates/*.py + test.
```

### 3.4 Decision engine + pipeline
```
UNIT: decision fold + run_clearance pipeline
SOURCE: /docs/08.
GOAL: run the chain, fold to the most severe verdict, short-circuit on BLOCK/FREEZE,
  seal the packet.
ACCEPTANCE: ALLOW only if all gates pass; first BLOCK/FREEZE stops the chain;
  returns (Decision, ProofPacket).
DELIVER: decision.py + pipeline.py + test.
```

### 3.5 Features (one prompt each — do not batch)
```
UNIT: clearance_token.py
SOURCE: /docs/03, /docs/09 (token threats), /docs/05 (/execution/attempt).
GOAL: HMAC-SHA256 token issued ONLY on ALLOW; a mock bank that rejects everything else.
DETAIL: token = b64(payload) + "." + b64(hmac_sha256(secret, payload)); payload =
  {run_id, vendor_id, amount, decision, ledger_head, exp}. issue_token returns None
  for non-ALLOW. mock_bank_execute rejects: NO_TOKEN, MALFORMED_TOKEN, TAMPERED_TOKEN
  (constant-time compare), NON_ALLOW_TOKEN, EXPIRED_TOKEN, VENDOR_MISMATCH,
  AMOUNT_MISMATCH, LEDGER_MISMATCH. Secret from env TOSCO_TOKEN_SECRET.
ACCEPTANCE: ALLOW→token→bank executes; FREEZE→no token→NO_TOKEN; tamper/vendor/amount/
  ledger/expiry each rejected.
DELIVER: clearance_token.py + test.
```
```
UNIT: counterfactual.py — Observe Mode
GOAL: given (ctx, final, scenario) return {observe_would_execute, counterfactual_loss,
  narrative}. clean→loss 0; injection→naive wires attacker amount (loss=amount);
  forgery→"The $X wire you didn't send" (loss=amount).
ACCEPTANCE: forgery loss==amount and narrative contains "didn't send"; clean loss==0.
DELIVER: counterfactual.py + test.
```
```
UNIT: evidence_locker.py
GOAL: assemble evidence_documents + sealed extraction + tool_calls + gate_results +
  decision into one dict embedded in the Proof Packet.
ACCEPTANCE: locker contains all five keys and a non-empty extraction sealed_hash.
DELIVER: evidence_locker.py + test.
```
```
UNIT: auditor.py — Auditor Export
GOAL: render a packet into a plain-language view: who_proposed, action, evidence_used,
  policy_version, gates (gate/outcome/why), decision, why_decision, hash_verified,
  chain_hash, sealed_at; plus a printable auditor_text().
ACCEPTANCE: view has all keys; hash_verified reflects ledger.verify(); text starts
  "PROOF PACKET".
DELIVER: auditor.py + test.
```
```
UNIT: sentinel.py — local attack memory
GOAL: on BLOCK/FREEZE record {workflow, vendor_id, amount, decision, reason_codes,
  failed_signals, recorded_at}; ui_message() → "Sentinel recorded attack pattern…".
  Local only. No network.
ACCEPTANCE: records on FREEZE with reason codes; returns None on ALLOW.
DELIVER: sentinel.py + test.
```
```
UNIT: ref_agent.py — Reference AP Agent
GOAL: build an ActionIntent per scenario (clean|injection|forgery) and POST
  /api/agent/propose then /api/runs/start. It proposes; it never decides.
ACCEPTANCE: returns a run_id; injection seed carries the poisoned instruction field.
DELIVER: ref_agent.py + test (can mock HTTP).
```

### 3.6 WorkflowDefinition loader
```
UNIT: engine/workflow.py
SOURCE: /docs/06.
GOAL: load + validate vendor_payment.yaml into a WorkflowDefinition model; expose
  gates_to_run, tools_to_call, decision_policy, etc. Reject unknown gate ids.
ACCEPTANCE: loads vendor_payment.yaml; a second YAML loads with zero core changes;
  bad gate id → clear error.
DELIVER: workflow.py + vendor_payment.yaml + test.
```

### 3.7 Orchestrator + event bus
```
UNIT: orchestrator.py + events.py
SOURCE: /docs/04 (events), /docs/08 (lifecycle).
GOAL: run the full lifecycle emitting, in order: PLAN_STARTED, EVIDENCE_RETRIEVED(×5),
  EXTRACTION_STARTED, EXTRACTION_SEALED, TOOL_CALLED(×tools), GATE_STARTED/GATE_COMPLETED
  (×gates), DECISION_MADE, TOKEN_ISSUED(if ALLOW), PROOF_SEALED, EXECUTION_ATTEMPTED.
  Persist everything to SQLite. Async queue per run for SSE.
ACCEPTANCE: event order is exactly as specified; a subscriber receives all events;
  state matches /api/runs/{id}.
DELIVER: orchestrator.py + events.py + test.
```

### 3.8 API + SSE + SQLite
```
UNIT: main.py (FastAPI) + db.py
SOURCE: /docs/05 (frozen contract), /docs/08 (schema).
GOAL: implement every route in 05 exactly, with the request/response/error shapes given.
  /events streams SSE; /verify recomputes live; /tamper-demo mutates one row;
  /execution/attempt calls the mock bank; /reset reseeds <30s.
CONSTRAINTS: no verdict logic in routes — routes call the engine; scenario picks seed
  data only, the pipeline always runs fully.
ACCEPTANCE: all /docs/10 acceptance tests 1–20 pass against the running server.
DELIVER: main.py + db.py + a test hitting the live app (httpx).
```

### 3.9 Vultr adapters
```
UNIT: extraction.py + evidence.py (Vultr)
SOURCE: /docs/04 (Vultr integration), /docs/13 (env).
GOAL: ExtractionSandbox → Vultr Serverless Inference (extract fields, seal output,
  schema-validate); EvidenceProvider → VultronRetriever (multi-pass). On any error or
  TOSCO_FALLBACK=true, fall back to local seeds and set fallback_mode=true.
CONSTRAINTS: injected instructions land only in non-decision fields; never executed.
  Log latency per call for the ToolCallLog. Never log the API key.
ACCEPTANCE: happy path returns a sealed extraction; forced failure → fallback_mode True,
  same gates still run.
DELIVER: extraction.py + evidence.py + test (mock the HTTP client).
```

### 3.10 React — Clearance Terminal (one component per prompt)
```
UNIT: <ComponentName> (React, Vite)
SOURCE: /docs/07 (design system — palette, type, motion), /docs/05 (data), /docs/04 (events).
GOAL: build <ComponentName> per doc 07. Consume state from the events store only; never
  compute a verdict. Use the palette tokens and the two fonts. Motion fires only on the
  named backend event. Respect prefers-reduced-motion.
COMPONENTS (build in this order): api.js (fetch+SSE store) → ScenarioSwitcher →
  LiveTimeline → GateChain/GateNode → DecisionCard → ClearanceTokenCard →
  MockBankExecutionCard → ProofSeal → ProofPacketViewer → HashVerifier + TamperDemoButton
  → ObserveModeCounterfactual → SentinelMemoryCard → NaiveAgentStrip → DocumentPreview →
  ActionIntentPanel → ReferenceAPAgentCard → EvidencePassCard → ToolCallLog → SandboxBadge.
ACCEPTANCE: <named behavior — e.g. GateNode flips only on GATE_COMPLETED; ProofSeal
  presses only on PROOF_SEALED>.
DELIVER: the component file + where it mounts. Tailwind core classes only or plain CSS
  with the doc-07 tokens.
```

### 3.11 The Proof Seal (special)
```
UNIT: ProofSeal.jsx
SOURCE: /docs/07 (3D Proof Seal direction).
GOAL: an SVG guilloche rosette in brass (--seal) on ink; on PROOF_SEALED it "presses"
  (scale 1.06→1.0, 3° rotate, 250ms) with the SHA-256 set in IBM Plex Mono around the rim.
CONSTRAINTS: pure SVG + CSS transform; no heavy 3D lib; respect reduced-motion.
ACCEPTANCE: renders idle; animates once on PROOF_SEALED; hash text is the real chain_hash.
DELIVER: ProofSeal.jsx + usage.
```

---

## 4. Reusable meta-prompts

**Review / harden:**
```
Review this file as a principal engineer for correctness, determinism, and security.
List concrete defects by severity (Critical/High/Med/Low). Then rewrite only the parts
that need it. Do not add features. Check especially: verdict-on-client leaks, unsealed
extraction reaching a gate, non-constant-time compares, swallowed errors, secrets in logs.
```

**Debug (paste the error):**
```
Here is the failing test output and the file. Diagnose the root cause in one line, then
give the minimal diff that makes the test pass without weakening any invariant. If the
test itself is wrong per /docs, say so and fix the test.
```

**Refactor to spec:**
```
This works but drifts from /docs/<n>. Realign it to the doc exactly — same names, same
routes, same event order — without changing behavior the acceptance tests rely on.
```

**Consistency sweep:**
```
Cross-check these files against /docs/05 (routes) and /docs/08 (models/events). Report
any mismatch in names, fields, decision values, or event order. Output a table:
file · symbol · doc-says · code-says · fix.
```

---

## 5. Forbid these (paste when the model gets lazy)
```
Do NOT: compute a verdict in the frontend; hardcode a decision in a scenario button;
use Streamlit; call it a "dashboard"; add a second real workflow; leave TODOs or
placeholders; invent stats; log secrets; skip the test; batch ten files when I asked
for one; weaken an invariant to make a test pass.
```

---

## 6. Golden rule
Prompt for **acceptance, not implementation.** Name the unit, cite the doc, state what must be *true* when done, demand a test. Then let the model write world-class code — and hold it to the invariants above every single time.
