# 02 — Hackathon Criteria

## Vultr Track (Statement 2) alignment
"Build a web-based Enterprise Agent for a real-world workflow that grounds its decisions in documents. The keyword is agent. A single retrieve-then-answer call is not enough."

TOSCO satisfies every clause:
- **Web-based enterprise agent:** React Clearance Terminal over a FastAPI clearance engine.
- **Grounds in documents:** decisions read invoice, PO, GRN, vendor master, policy pack.
- **Plans:** orchestrator plans the required evidence + gate set per workflow.
- **Retrieves more than once:** 5-pass retrieval via VultronRetriever.
- **Calls tools:** policy, risk, bank-owner, domain-age, logistics.
- **Makes decisions:** deterministic gates → ALLOW / ESCALATE / BLOCK / FREEZE.
- **Real enterprise outcome:** a cleared or blocked payment + signed token + Proof Packet.
- **Vultr:** Serverless Inference for extraction; VultronRetriever for retrieval (fallback labeled SANDBOX).

## Judging criteria mapping
- **Impact (25%):** $3.05B BEC problem; named CFO buyer; regulator-demanded category; ROI = one prevented wire.
- **Demo (50%):** live real-time pipeline; the injection block; the Reality-Gate FREEZE; signed bank rejection; live hash verify. It *works*, on real APIs.
- **Creativity (15%):** attack-and-defense side-by-side; naive agent approves the attacker payment while TOSCO detects the injected bank/routing mismatch and BLOCKS; "prompt-inject the model, not the math"; the Proof Seal.
- **Pitch (10%):** heist-framed 60s; one unforgettable line; no slides.

## Banned-project avoidance
Not a Streamlit app (React). Not a basic RAG app (multi-step, tool-calling, deterministic decision). Not dashboard-first (the pipeline is the product; never say "dashboard"). Not an invoice parser (extraction is one caged step). Not a fraud-detection toy (pre-execution authority, not post-hoc scoring).

## Why not basic RAG
Retrieve-then-answer cannot plan, retrieve multiple times, call tools, or produce a governed decision. TOSCO does all four and the LLM never decides — it only extracts.

## Why not dashboard-first
There are no charts as the main artifact. What renders is the clearance *happening* — gate nodes flipping on real backend events, a decision landing, a token issued, a bank accepting or rejecting.

## Why agentic
A Reference AP Agent proposes an action; TOSCO runs a multi-step governed workflow (plan → retrieve → extract → tools → gates → decide → seal → enforce) and returns an enterprise outcome. Multi-step, tool-using, stateful per run.

## Required proof points for judges (must all be visible live)
1. Multi-pass retrieval shown in the timeline.
2. Vultr inference call visible in the tool/log pane.
3. Injection: naive agent APPROVES the attacker payment; TOSCO detects the injected payment-routing / bank mismatch / suspicious instruction and BLOCKS; no valid ALLOW token is issued; Mock Bank rejects execution.
4. Forgery: document gates pass, Reality Gate fails → FREEZE.
5. Clearance token issued only on ALLOW.
6. Mock bank rejects every non-ALLOW / invalid token.
7. Proof Packet hash verifies live; tamper breaks it.
8. Workflow loaded from YAML (genericity), not hardcoded.
