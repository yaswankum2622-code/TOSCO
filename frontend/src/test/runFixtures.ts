import type {
  ContractRunEvent,
  GateResultPayload,
  RunSnapshotResponse,
  ToolCallPayload
} from "../api/types";

type DecisionKind = "ALLOW" | "BLOCK" | "FREEZE";

function scenarioForDecision(decision: DecisionKind): "clean" | "injection" | "forgery" {
  switch (decision) {
    case "ALLOW":
      return "clean";
    case "BLOCK":
      return "injection";
    case "FREEZE":
      return "forgery";
  }
}

function runIdForScenario(scenario: string): string {
  return `run-${scenario}-001`;
}

function proofHashForScenario(scenario: string): string {
  const prefix = scenario === "clean" ? "a" : scenario === "injection" ? "b" : "c";
  return prefix.repeat(64);
}

function tokenForScenario(scenario: string): string {
  return JSON.stringify({
    token_version: "1.0",
    token_id: `tok-${scenario}-001`,
    run_id: runIdForScenario(scenario),
    workflow_id: "vendor_payment",
    decision: "ALLOW",
    vendor_id: "VEND-ACME-001",
    amount: 340000,
    currency: "USD",
    bank_account_last4: "8821",
    packet_hash: proofHashForScenario(scenario),
    ledger_entry_hash: `${scenario[0]}`.repeat(64),
    issued_at: "2026-07-04T12:00:00Z",
    expires_at: "2026-07-04T12:10:00Z",
    signature: "d".repeat(64)
  });
}

function gatePayloads(decision: DecisionKind): GateResultPayload[] {
  const groundedness =
    decision === "BLOCK"
      ? {
          gate_id: "G2_GROUNDEDNESS",
          name: "Groundedness",
          status: "FAIL",
          decision: "BLOCK",
          reason_code: "BANK_ACCOUNT_MISMATCH",
          human_reason: "Typed extraction does not match vendor master.",
          evidence_refs: ["invoice", "vendor_master"]
        }
      : {
          gate_id: "G2_GROUNDEDNESS",
          name: "Groundedness",
          status: "PASS",
          decision: "ALLOW",
          reason_code: "FIELDS_GROUNDED",
          human_reason: "Required fields were grounded to source spans.",
          evidence_refs: ["invoice", "vendor_master"]
        };

  const risk =
    decision === "FREEZE"
      ? {
          gate_id: "G4_RISK",
          name: "Risk",
          status: "WARN",
          decision: "ESCALATE",
          reason_code: "RECENT_BANK_CHANGE",
          human_reason: "Bank change was recent and first-pay-to-account risk is elevated.",
          evidence_refs: ["invoice", "vendor_master"]
        }
      : {
          gate_id: "G4_RISK",
          name: "Risk",
          status: "PASS",
          decision: "ALLOW",
          reason_code: "RISK_ACCEPTABLE",
          human_reason: "Typed risk signals were acceptable.",
          evidence_refs: ["invoice", "vendor_master"]
        };

  const reality =
    decision === "FREEZE"
      ? {
          gate_id: "G5_REALITY",
          name: "Reality",
          status: "FAIL",
          decision: "FREEZE",
          reason_code: "REALITY_OWNER_MISMATCH_FREEZE",
          human_reason: "Reality checks contradicted the updated bank account ownership.",
          evidence_refs: ["vendor_master"]
        }
      : {
          gate_id: "G5_REALITY",
          name: "Reality",
          status: "PASS",
          decision: "ALLOW",
          reason_code: "REALITY_CONFIRMED",
          human_reason: "Reality checks confirmed the payment instructions.",
          evidence_refs: ["vendor_master"]
        };

  return [
    {
      gate_id: "G1_EVIDENCE",
      name: "Evidence",
      status: "PASS",
      decision: "ALLOW",
      reason_code: "EVIDENCE_COMPLETE",
      human_reason: "All required evidence is present.",
      evidence_refs: ["invoice", "po", "grn", "vendor_master", "policy_pack"]
    },
    groundedness,
    {
      gate_id: "G3_POLICY",
      name: "Policy",
      status: "PASS",
      decision: "ALLOW",
      reason_code: "HIGH_VALUE_POLICY_REQUIRES_REALITY_GATE",
      human_reason: "High-value policy is satisfied pending the reality gate.",
      evidence_refs: ["policy_pack"]
    },
    risk,
    reality,
    {
      gate_id: "G6_DECISION_SEAL",
      name: "Decision Seal",
      status: decision === "ALLOW" ? "PASS" : "WARN",
      decision,
      reason_code: decision === "ALLOW" ? "DECISION_SEAL_READY" : "DECISION_SEAL_BLOCKED",
      human_reason: decision === "ALLOW" ? "Ready to seal." : "Seal blocked by prior gate outcomes.",
      evidence_refs: ["G1_EVIDENCE", "G2_GROUNDEDNESS", "G3_POLICY", "G4_RISK", "G5_REALITY"]
    }
  ];
}

function toolCalls(): ToolCallPayload[] {
  return [
    {
      tool_id: "policy_tool",
      input: { run_id: "run" },
      output: { tool_id: "policy_tool", signal_keys: ["bank_owner_matches_vendor", "request_domain_age_days"] },
      simulated: true,
      latency_ms: null
    },
    {
      tool_id: "risk_tool",
      input: { run_id: "run" },
      output: { tool_id: "risk_tool", signal_keys: ["velocity_risk", "duplicate_invoice"] },
      simulated: true,
      latency_ms: null
    }
  ];
}

function evidenceRefsForScenario(scenario: "clean" | "injection" | "forgery"): string[] {
  if (scenario === "clean") {
    return [
      "invoice-clean-1",
      "po-clean-2",
      "grn-clean-3",
      "vendor_master-clean-4",
      "policy_pack-clean-5"
    ];
  }
  if (scenario === "injection") {
    return [
      "invoice-injection-1",
      "po-injection-2",
      "grn-injection-3",
      "vendor_master-injection-4",
      "policy_pack-injection-5"
    ];
  }
  return [
    "invoice-forgery-1",
    "po-forgery-2",
    "grn-forgery-3",
    "vendor_master-forgery-4",
    "policy_pack-forgery-5"
  ];
}

export function makeContractSequence(
  decision: DecisionKind,
  options: { fallbackMode?: boolean } = {}
): ContractRunEvent[] {
  const scenario = scenarioForDecision(decision);
  const runId = runIdForScenario(scenario);
  const fallbackMode = options.fallbackMode ?? false;
  const token = decision === "ALLOW" ? tokenForScenario(scenario) : null;
  const proofHash = proofHashForScenario(scenario);
  const gateResults = gatePayloads(decision);
  const finalReasonCodes = gateResults.map((gate) => gate.reason_code);

  return [
    {
      event: "PLAN_STARTED",
      run_id: runId,
      ts: "2026-07-04T12:00:00Z",
      data: {
        workflow_id: "vendor_payment",
        workflow_name: "AI Vendor Payment & Bank-Change Clearance"
      }
    },
    ...[
      "invoice",
      "po",
      "grn",
      "vendor_master",
      "policy_pack"
    ].map((evidenceType, index) => ({
      event: "EVIDENCE_RETRIEVED",
      run_id: runId,
      ts: "2026-07-04T12:00:01Z",
      data: {
        retrieval_pass: index + 1,
        total_passes: 5,
        evidence_type: evidenceType,
        evidence_types: ["invoice", "po", "grn", "vendor_master", "policy_pack"],
        evidence_count: 5,
        doc_id: evidenceRefsForScenario(scenario)[index]
      }
    })),
    {
      event: "EXTRACTION_STARTED",
      run_id: runId,
      ts: "2026-07-04T12:00:02Z",
      data: {
        extractor: fallbackMode ? "sandbox-fallback" : "vultr-serverless-inference",
        fallback_mode: fallbackMode
      }
    },
    {
      event: "EXTRACTION_SEALED",
      run_id: runId,
      ts: "2026-07-04T12:00:03Z",
      data: {
        extraction_hash: "e".repeat(64),
        required_fields: ["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        fallback_mode: fallbackMode
      }
    },
    ...toolCalls().map((toolCall, index) => ({
      event: "TOOL_CALLED",
      run_id: runId,
      ts: "2026-07-04T12:00:04Z",
      data: {
        tool_id: toolCall.tool_id,
        simulated: toolCall.simulated,
        signal_keys: toolCall.output.signal_keys as string[],
        order: index
      }
    })),
    ...gateResults
      .filter((gate) => gate.gate_id !== "G6_DECISION_SEAL")
      .flatMap((gate) => [
        {
          event: "GATE_STARTED",
          run_id: runId,
          ts: "2026-07-04T12:00:05Z",
          data: {
            gate_id: gate.gate_id
          }
        },
        {
          event: "GATE_COMPLETED",
          run_id: runId,
          ts: "2026-07-04T12:00:06Z",
          data: {
            gate_id: gate.gate_id,
            status: gate.status,
            decision: gate.decision,
            reason_code: gate.reason_code,
            human_reason: gate.human_reason
          }
        }
      ]),
    {
      event: "DECISION_MADE",
      run_id: runId,
      ts: "2026-07-04T12:00:07Z",
      data: {
        final_decision: decision,
        status: decision === "ALLOW" ? "APPROVED" : decision === "BLOCK" ? "BLOCKED" : "FROZEN",
        allow_execution: decision === "ALLOW",
        reason_codes: finalReasonCodes
      }
    },
    ...(decision === "ALLOW"
      ? [
          {
            event: "TOKEN_ISSUED",
            run_id: runId,
            ts: "2026-07-04T12:00:08Z",
            data: {
              token_id: `tok-${scenario}-001`,
              expires_at: "2026-07-04T12:10:00Z",
              token
            }
          } satisfies ContractRunEvent
        ]
      : []),
    {
      event: "PROOF_SEALED",
      run_id: runId,
      ts: "2026-07-04T12:00:09Z",
      data: {
        proof_hash: proofHash,
        final_decision: decision
      }
    },
    {
      event: "EXECUTION_ATTEMPTED",
      run_id: runId,
      ts: "2026-07-04T12:00:10Z",
      data: {
        token_id: decision === "ALLOW" ? `tok-${scenario}-001` : null,
        amount: 340000,
        bank_account_last4: decision === "BLOCK" ? "0009" : decision === "FREEZE" ? "7730" : "8821",
        executed: decision === "ALLOW",
        reason: decision === "ALLOW" ? "CLEARED" : "NO_TOKEN"
      }
    }
  ];
}

export function makeSnapshot(decision: DecisionKind): RunSnapshotResponse {
  const scenario = scenarioForDecision(decision);
  return {
    run_id: runIdForScenario(scenario),
    workflow_id: "vendor_payment",
    status: "COMPLETED",
    intent: {
      intent_id: `intent-${scenario}-001`,
      agent_id: "reference-ap-agent",
      workflow: "vendor_payment",
      action: {
        type: "payment",
        vendor_id: "VEND-ACME-001",
        amount: 340000,
        currency: "USD",
        bank_account_last4: decision === "BLOCK" ? "0009" : decision === "FREEZE" ? "7730" : "8821"
      },
      evidence_refs: [
        "grn",
        "invoice",
        "po",
        "policy-pack-v1",
        "vendor-master"
      ],
      declared_confidence: 0.94,
      requested_mode: "assisted"
    },
    evidence_refs: evidenceRefsForScenario(scenario),
    extraction_hash: "e".repeat(64),
    tool_calls: toolCalls(),
    gate_results: gatePayloads(decision),
    decision,
    fallback_mode: false,
    clearance_token: decision === "ALLOW" ? tokenForScenario(scenario) : null,
    error_message: null
  };
}
