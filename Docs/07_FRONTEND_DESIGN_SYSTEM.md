# 07 — Frontend Design System · "Clearance Terminal"

**Direction:** security-printing meets settlement desk. An enterprise financial command room — premium, cinematic, controlled, quiet. Deliberately NOT a SaaS dashboard, NOT dark-neon AI, NOT noisy.

## Color palette
```
--ink       #101C2C   deep ledger-ink navy   (app background)
--ink-2     #16243A   raised panels
--paper     #E9E4D8   document cards (invoices render on "paper" over ink)
--paper-ink #23303F   text on paper
--clear     #2E7D5B   ALLOW / verified / pass
--block     #C0392B   BLOCK / FREEZE / fail
--warn      #C98A2F   ESCALATE / warning
--seal      #B98A2F   brass — Proof Seal, hashes, money
--mute      #6B7686   labels, secondary text
--line      #24344A   hairlines, node connectors
```
Green and red appear ONLY on decisions. Brass ONLY on seal + hashes + money. Everything else navy/paper/mute — so the verdict colors carry meaning.

## Typography
- **Archivo** (600/700, tight tracking) — headings, decisions, gate names.
- **IBM Plex Mono** — money, hashes, gate codes, token, tool latencies (evidence reads as evidence).
Two faces only. Self-host woff2 for offline demo. Scale: 12 / 14 / 16 / 20 / 28 / 40.

## Layout (3 columns on ink)
```
┌ LEFT (proposer + inputs) ┬ CENTER (the clearance runs) ┬ RIGHT (outcome + proof) ┐
│ ScenarioSwitcher         │ LiveTimeline                │ DecisionCard            │
│ ReferenceAPAgentCard     │ EvidencePassCard ×5         │ ClearanceTokenCard      │
│ ActionIntentPanel        │ ToolCallLog                 │ MockBankExecutionCard   │
│ DocumentPreview (paper)  │ NaiveAgentStrip (thin, top) │ ObserveModeCounterfactual│
│                          │ GateChain → GateNode ×5     │ ProofSeal               │
│                          │                             │ ProofPacketViewer       │
│                          │                             │ HashVerifier + TamperDemoButton │
│                          │                             │ SentinelMemoryCard      │
└──────────────────────────┴─────────────────────────────┴─────────────────────────┘
SandboxBadge — fixed top-right, brass outline, always visible.
```

## Component behavior (motion tied ONLY to backend events)
- **GateChain / GateNode:** 5 connected nodes. A node is `idle → running → pass/fail`. It flips ONLY on `GATE_COMPLETED`. Pass = clear green fill; fail = block red + subtle shake once.
- **LiveTimeline:** appends a row per event (`PLAN_STARTED`…`EXECUTION_ATTEMPTED`), mono, timestamped.
- **EvidencePassCard:** one per retrieval pass; appears on `EVIDENCE_RETRIEVED`.
- **ToolCallLog:** appends on `TOOL_CALLED` with tool id + latency (shows real Vultr calls).
- **NaiveAgentStrip:** thin strip; on injection scenario flashes `APPROVED` in red to contrast TOSCO.
- **DecisionCard:** renders on `DECISION_MADE` — verdict + one plain sentence.
- **ClearanceTokenCard:** renders on `TOKEN_ISSUED` (ALLOW only); shows truncated token + exp.
- **MockBankExecutionCard:** renders on `EXECUTION_ATTEMPTED`; green "Executed" or red "Rejected — <reason>".
- **ObserveModeCounterfactual:** shows "would have executed" + the counterfactual amount banner on attacks.
- **ProofSeal:** renders + **presses** (scale 1.06→1.0, 250ms) on `PROOF_SEALED`.
- **HashVerifier:** button → `/verify`; links flip green; TamperDemoButton → `/tamper-demo` then re-verify shows red.
- **SentinelMemoryCard:** on BLOCK/FREEZE shows "Sentinel recorded attack pattern" + reason codes.

## Animation rules
- Gate stagger 150ms (masks Vultr latency). One orchestrated moment per act, nothing gratuitous.
- BLOCK = full-screen takeover card sliding up, red stamp.
- Respect `prefers-reduced-motion` (cut animation, keep state).

## 3D Proof Seal direction
Guilloche rosette (layered rotated ellipses / SVG `<path>` spirograph) in brass on ink. On seal it "presses": a quick scale-down + a 3° rotate + a soft inner-shadow, with the SHA-256 set in Plex Mono around the rim. This is the one signature visual; keep everything else restrained so it owns the memory.

## What NOT to do
No charts-as-hero. No gradient buttons. No emoji. No more than two fonts. No color outside the palette. Never the word "dashboard" in UI copy. No verdict computed client-side. No animation firing ahead of a backend event.
