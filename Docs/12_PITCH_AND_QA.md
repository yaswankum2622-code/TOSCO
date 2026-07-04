# 12 — Pitch & QA

## 10-second
"TOSCO is the clearance layer AI agents must pass through before they move money. The model extracts; deterministic gates decide; every decision is signed and provable."

## 30-second
"Enterprises are letting AI agents initiate payments — which makes the agent the fraud vector: a poisoned invoice hijacks it, a perfect forgery clears every check. $3.05B lost to BEC last year. TOSCO sits before execution. The LLM only extracts. Deterministic gates — evidence, policy, risk, and a Reality Gate that checks signals a forger can't control — decide ALLOW, ESCALATE, or BLOCK. When a poisoned invoice tries to redirect the payment, TOSCO catches the bank/routing mismatch and BLOCKS — no signed token, so our mock bank executes nothing. Every decision seals into a hash-chained Proof Packet. You can prompt-inject the model. You can't prompt-inject the math."

## 60-second demo narration
"Meridian's AP agent proposes a $340,000 vendor payment. [Golden] TOSCO plans, retrieves the invoice, PO, goods receipt and vendor master, extracts on Vultr, runs the gates — all green — ALLOW. A signed clearance token is issued and the mock bank executes. [Injection] Now a poisoned invoice with hidden text telling the agent to pay a different account. The naive agent approves the attacker payment. TOSCO detects the injected bank/routing mismatch — the proposed account doesn't match the verified vendor master — and BLOCKS; no token is issued, the bank rejects. Write your own attack — still blocked. You can prompt-inject the model; you can't prompt-inject the math. [Forgery] A flawless forged pack — invoice, PO, receipt all consistent. Document gates pass. The Reality Gate fires: bank owner doesn't match, twelve-day-old domain, no shipment. FREEZE. No token. Bank rejects. This is the $340,000 wire you didn't send. Sentinel records the attack. [Proof] One click — the Proof Packet, hash-chain verified live; I tamper one row and verification fails. Agents propose. TOSCO clears. Execution obeys. Audit proves."

## 3-minute judge pitch (structure)
1. Problem (20s): agents + money = new attack surface; $3.05B BEC; regulators demand a decision/execution split.
2. Category (15s): pre-execution clearance; not detection, not observability.
3. Live demo (110s): the 60s arc + show YAML-driven genericity + real Vultr calls in the log.
4. Why it wins (20s): the LLM never decides; enforcement via signed token; audit-grade proof.
5. Roadmap (15s): plugin workflows (KYC/AML/covenant), design partners, Proof Packet as audit standard.

## 10 judge questions + answers
1. *Would gates survive real invoices?* — "Unknown; every screen says SANDBOX. Buyer is pre-production; next rung is shadow-mode replay on their historical data."
2. *Isn't the naive agent a strawman?* — "It's the standard retrieve-then-act pattern — the common architecture. The default is the vulnerability."
3. *Where's the AI if the model can't decide?* — "Caged on purpose — extraction only. Competitors put the model in the decision seat; regulators call that unauditable. Minimal AI is the product."
4. *Reality Gate signals are simulated?* — "Provider interface is real, signals staged; bank-verification/registry APIs drop in behind it."
5. *What stops the agent bypassing TOSCO?* — "The rail requires a signed clearance token; no token, no execution. We show a bypass attempt getting rejected."
6. *Is the token real crypto?* — "HMAC-SHA256 bound to vendor+amount+ledger head, short expiry; tamper/mismatch/expiry all rejected live."
7. *How is this not RAG?* — "It plans, retrieves five docs across passes, calls tools, and decides — retrieve-then-answer does none of that."
8. *How is this not a dashboard?* — "The product is the decision pipeline; you're watching clearance happen over real APIs."
9. *No real money?* — "Correct — sandbox rail, labeled. It proves the full control loop with zero risk."
10. *Adaptable to other workflows?* — "The engine loads a YAML; a new workflow is config + plugins. We ship a bank-change skeleton to prove it, without building it."

## Explaining Vultr usage
"Extraction runs on Vultr Serverless Inference; multi-pass retrieval on VultronRetriever — both visible live in the tool log. If either is unavailable we fall back locally and label it SANDBOX."
