import type { AgentProposeRequest } from "./types";

const REFERENCE_PROPOSALS: Record<string, AgentProposeRequest> = {
  clean: {
    agent_id: "reference-ap-agent",
    workflow: "vendor_payment",
    action: {
      type: "payment",
      vendor_id: "VEND-ACME-001",
      amount: 340000,
      currency: "USD",
      bank_account_last4: "8821"
    },
    evidence_refs: [
      "grn-clean-881",
      "invoice-clean-1048",
      "po-clean-881",
      "policy-pack-v1",
      "vendor-master-acme"
    ],
    declared_confidence: 0.94,
    requested_mode: "assisted",
    scenario: "clean"
  },
  injection: {
    agent_id: "reference-ap-agent",
    workflow: "vendor_payment",
    action: {
      type: "payment",
      vendor_id: "VEND-ACME-001",
      amount: 340000,
      currency: "USD",
      bank_account_last4: "0009"
    },
    evidence_refs: [
      "grn-clean-881",
      "invoice-injection-1048",
      "po-clean-881",
      "policy-pack-v1",
      "vendor-master-acme"
    ],
    declared_confidence: 0.94,
    requested_mode: "assisted",
    scenario: "injection"
  },
  forgery: {
    agent_id: "reference-ap-agent",
    workflow: "vendor_payment",
    action: {
      type: "payment",
      vendor_id: "VEND-ACME-001",
      amount: 340000,
      currency: "USD",
      bank_account_last4: "7730"
    },
    evidence_refs: [
      "grn-forgery-2091",
      "invoice-forgery-7730",
      "po-forgery-2091",
      "policy-pack-v1",
      "vendor-master-acme-updated"
    ],
    declared_confidence: 0.94,
    requested_mode: "assisted",
    scenario: "forgery"
  }
};

export function buildScenarioProposalRequest(scenario: string): AgentProposeRequest {
  const proposal = REFERENCE_PROPOSALS[scenario];
  if (!proposal) {
    throw new Error(`No reference proposal exists for scenario '${scenario}'.`);
  }

  return {
    ...proposal,
    action: { ...proposal.action },
    evidence_refs: [...proposal.evidence_refs]
  };
}
