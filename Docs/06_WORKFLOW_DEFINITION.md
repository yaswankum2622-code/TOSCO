# 06 — Workflow Definition

## Schema (`WorkflowDefinition`)
```
workflow_id: str
workflow_name: str
required_evidence_types: [str]        # what EvidenceProvider must retrieve
extraction_schema:
  required_fields: [str]              # ExtractionSandbox validates against these
gates_to_run: [str]                  # gate plugin ids, in order
tools_to_call: [str]                 # ToolProvider ids
decision_policy:
  allow_requires_all_pass: bool
  high_value_threshold: number
  reality_required_above: number     # internal consistency alone caps at ESCALATE above this
  mandatory_human_confirm: bool (optional)
proof_packet_template: str
execution_adapter: "sandbox" | "<connector>"
```

## `vendor_payment.yaml` (the live workflow)
```yaml
workflow_id: vendor_payment
workflow_name: AI Vendor Payment & Bank-Change Clearance
required_evidence_types: [invoice, po, grn, vendor_master, policy_pack]
extraction_schema:
  required_fields: [invoice_id, vendor_name, amount, bank_account_last4]
gates_to_run: [G1_EVIDENCE, G2_GROUNDEDNESS, G3_POLICY, G4_RISK, G5_REALITY]
tools_to_call: [policy_tool, risk_tool, bank_owner_check, domain_age_check, logistics_check]
decision_policy:
  allow_requires_all_pass: true
  high_value_threshold: 50000
  reality_required_above: 50000
proof_packet_template: vendor_payment_proof
execution_adapter: sandbox
```

## Evidence, extraction, tools, gates, policy, proof, adapter
- **Required evidence:** invoice, PO, GRN, vendor master, policy pack (5 retrieval passes).
- **Extraction schema:** invoice_id, vendor_name, amount, bank_account_last4 (missing → G1 REQUEST_MORE_EVIDENCE).
- **Tools:** policy_tool, risk_tool, bank_owner_check, domain_age_check, logistics_check.
- **Gates:** G1 evidence · G2 groundedness · G3 policy · G4 risk · G5 reality.
- **Decision policy:** ALLOW only if all pass; high-value (≥50k) requires ≥1 external confirmation, else ESCALATE cap; owner mismatch → FREEZE.
- **Proof template:** `vendor_payment_proof` (sections: intent, evidence, extraction, tools, gates, decision, hashes).
- **Execution adapter:** sandbox (Mock Bank).

## Adding a workflow later (no core change)
1. Write `new_workflow.yaml`.
2. Add any new gate plugins (`@gate("GX_...")`) and tool providers.
3. Provide an evidence schema + proof template.
The orchestrator loads the YAML and runs it. **We ship `vendor_bank_change.yaml` as a SKELETON only** — proof of extensibility, not a second build.
