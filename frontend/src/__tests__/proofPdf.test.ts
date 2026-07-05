import { describe, expect, it } from "vitest";

import { createInitialRunState } from "../run/store";
import { buildProofPacketPdf } from "../utils/proofPdf";

describe("proofPdf", () => {
  it("builds a one-page sandbox PDF with decision and chain hash", () => {
    const state = createInitialRunState();
    state.runId = "run-clean-001";
    state.scenario = "clean";
    state.workflow = "vendor_payment";
    state.proposal = {
      request: {
        agent_id: "reference-ap-agent",
        workflow: "vendor_payment",
        action: {
          type: "payment",
          vendor_id: "VEND-ACME-001",
          amount: 340000,
          currency: "USD",
          bank_account_last4: "8821"
        },
        evidence_refs: ["invoice-clean-1048"],
        declared_confidence: 0.94,
        requested_mode: "assisted",
        scenario: "clean"
      },
      intentId: "intent-clean-001",
      accepted: true
    };
    state.gates = state.gates.map((gate) =>
      gate.id === "G2_GROUNDEDNESS"
        ? { ...gate, status: "PASS", reasonCode: "FIELDS_GROUNDED", humanReason: "Grounded" }
        : gate
    );
    state.decision = { value: "ALLOW", humanReason: "FIELDS_GROUNDED" };
    state.proof = { sealed: true, chainHash: "a".repeat(64) };
    state.verification = {
      verified: true,
      chainHead: "b".repeat(64),
      proofHash: "a".repeat(64),
      ledgerEntryHash: "b".repeat(64),
      ledgerChainValid: true,
      packetEntryValid: true,
      tamperedField: null
    };

    const doc = buildProofPacketPdf(state);

    expect(doc.getNumberOfPages()).toBe(1);
    const bytes = doc.output("arraybuffer");
    expect(bytes.byteLength).toBeGreaterThan(500);
  });
});
