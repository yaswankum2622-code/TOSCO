# 01 — Product Vision

## One-sentence vision
TOSCO is the independent pre-execution clearance layer for the agent economy — the control plane every AI agent must pass through before it can move money.

## Category
**Pre-execution clearance for agentic financial actions.** Not fraud detection (post-hoc — tells you money left). Not observability (records what happened). Not AI governance paperwork (governs models, not transactions). TOSCO clears an action *before* it executes and emits cryptographic proof of *why* it was permitted. The category primitive is the **Proof Packet**; the enforcement primitive is the **Clearance Token**.

## Why now
Three curves crossed in 2026. **Adoption:** Gartner projects 40% of enterprise apps carry task-specific agents by end 2026 (from <5% in 2025). **Attack economics:** prompt injection is the fastest-growing attack class; BEC losses hit a reported $3.05B in 2025 (FBI IC3); 76% of orgs faced payments fraud, 74% via BEC (AFP 2026). **Regulation:** the IMF (Apr 2026) calls for architectural separation of decision and execution; NIST notes risk frameworks stop at the model boundary; Singapore mandates verifiable agent authorization trails. The danger, the demand, and the mandate arrived together — and the authority seat is empty.

## Buyer / user
- **Economic buyer:** CFO / VP Finance — owns fraud loss + audit cost.
- **Daily user:** AP controller — clears escalations from a 30-second card.
- **Security stakeholder:** CISO — owns the "agent is an insider" threat.
- **Compliance stakeholder:** CCO — owns EU AI Act / Treasury AI RMF exposure.
- **Integration owner:** platform / AI engineering — wires the agent to TOSCO via REST/MCP.

## What TOSCO is / is not
**Is:** a pre-execution control layer · enterprise financial infrastructure · AI safety for money movement · a payment firewall for agentic finance · an audit-grade clearance system.
**Is not:** a chatbot · a dashboard · an invoice parser · a fraud-detection toy · a Streamlit app · a basic RAG app.

## One workflow now, many later
The hackathon builds **one workflow deeply — AI Vendor Payment & Bank-Change Clearance** — on an engine that is workflow-agnostic by configuration. A second workflow (KYC, AML, covenant, claims, procurement) is a new `WorkflowDefinition` YAML + gate plugins, never a core rewrite. We prove this with a `vendor_bank_change.yaml` skeleton; we do **not** build it.

## Special features in hackathon scope
1. Observe Mode Counterfactual — "the $340,000 wire you didn't send."
2. Clearance Token — HMAC-SHA256, issued only on ALLOW; enforcement, not advice.
3. Evidence Locker — every input to the decision, sealed into the Proof Packet.
4. Auditor Export — plain-language proof view.
5. Sentinel Attack Memory — local record of every BLOCK/FREEZE pattern.
6. Mock Bank Execution Adapter — accepts only valid ALLOW tokens.
7. Reference AP Agent — proposes payments so the demo is a real orchestration.
8. Tamper Demo — mutate a ledger row, watch verification fail.

*Agents propose. TOSCO clears. Execution obeys. Audit proves.*
