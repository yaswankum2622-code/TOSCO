import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  apiClient: {
    getHealth: vi.fn(),
    getVultrStatus: vi.fn(),
    getWorkflows: vi.fn(),
    getScenarios: vi.fn(),
    startRun: vi.fn(),
    listRuns: vi.fn(),
    getRun: vi.fn(),
    getEvents: vi.fn(),
    getProof: vi.fn(),
    verifyRun: vi.fn(),
    tamperRun: vi.fn(),
    resetDemo: vi.fn()
  }
}));

const mockedApiClient = vi.mocked(apiClient);

const workflows = [
  {
    workflow_id: "vendor_payment",
    workflow_name: "AI Vendor Payment & Bank-Change Clearance",
    required_evidence_types: ["invoice", "po", "grn", "vendor_master"],
    gates_to_run: [
      "G1_EVIDENCE",
      "G2_GROUNDEDNESS",
      "G3_POLICY",
      "G4_RISK",
      "G5_REALITY",
      "G6_DECISION_SEAL"
    ],
    tools_to_call: ["policy_tool", "risk_tool", "bank_owner_check"],
    execution_adapter: "sandbox"
  }
];

const scenarios = [
  {
    scenario: "clean",
    title: "Clean Payment",
    description: "Legitimate invoice, PO, and goods receipt.",
    expected_naive_agent_action: "Approve vendor payment",
    expected_tosco_decision: "ALLOW"
  }
];

function makeRunSummary() {
  return {
    scenario: "clean",
    run_id: "clean-run-001",
    final_decision: "ALLOW",
    allow_execution: true,
    token_issued: true,
    mock_bank_status: "ACCEPTED",
    mock_bank_reason_code: "EXECUTION_ACCEPTED",
    proof_hash: "a".repeat(64),
    ledger_entry_hash: "b".repeat(64),
    timeline_events_count: 20
  };
}

function makeTimeline(withFallback = false) {
  const events = [
    {
      index: 0,
      event_type: "AGENT_PROPOSED",
      run_id: "clean-run-001",
      title: "Agent Proposed Payment",
      detail: "The reference AP agent proposed a payment action from seeded documents.",
      payload: {
        scenario: "clean",
        naive_action: "Approve vendor payment",
        vendor_id: "V-1042",
        amount: 340000,
        bank_account_last4: "8821"
      }
    },
    {
      index: 1,
      event_type: withFallback ? "VULTR_EXTRACTION_FALLBACK" : "VULTR_EXTRACTION_SUCCEEDED",
      run_id: "clean-run-001",
      title: withFallback ? "Vultr Extraction Fallback" : "Vultr Extraction Succeeded",
      detail: withFallback
        ? "Vultr extraction failed, so TOSCO fell back to the seeded deterministic extraction."
        : "Vultr returned structured extraction data.",
      payload: {
        model: "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
        error_code: withFallback ? "VULTR_NOT_CONFIGURED" : undefined
      }
    },
    {
      index: 2,
      event_type: "EVIDENCE_RETRIEVED",
      run_id: "clean-run-001",
      title: "Evidence Retrieved",
      detail: "Seeded evidence was loaded for the clearance run.",
      payload: {
        evidence_types: ["invoice", "po", "grn", "vendor_master"],
        evidence_count: 4
      }
    },
    {
      index: 3,
      event_type: "EXTRACTION_SEALED",
      run_id: "clean-run-001",
      title: "Extraction Sealed",
      detail: "The extraction boundary was sealed before gates evaluated typed facts.",
      payload: {
        extraction_hash: "c".repeat(64),
        required_fields: ["invoice_id", "vendor_name", "amount", "bank_account_last4"]
      }
    },
    {
      index: 4,
      event_type: "GATE_COMPLETED",
      run_id: "clean-run-001",
      title: "Gate Completed",
      detail: "G1 completed.",
      payload: { gate_id: "G1_EVIDENCE", status: "PASS", decision: "ALLOW", reason_code: "EVIDENCE_COMPLETE" }
    },
    {
      index: 5,
      event_type: "GATE_COMPLETED",
      run_id: "clean-run-001",
      title: "Gate Completed",
      detail: "G2 completed.",
      payload: { gate_id: "G2_GROUNDEDNESS", status: "PASS", decision: "ALLOW", reason_code: "FIELDS_GROUNDED" }
    },
    {
      index: 6,
      event_type: "GATE_COMPLETED",
      run_id: "clean-run-001",
      title: "Gate Completed",
      detail: "G3 completed.",
      payload: { gate_id: "G3_POLICY", status: "PASS", decision: "ALLOW", reason_code: "POLICY_CLEAR" }
    },
    {
      index: 7,
      event_type: "GATE_COMPLETED",
      run_id: "clean-run-001",
      title: "Gate Completed",
      detail: "G4 completed.",
      payload: { gate_id: "G4_RISK", status: "PASS", decision: "ALLOW", reason_code: "RISK_CLEAR" }
    },
    {
      index: 8,
      event_type: "GATE_COMPLETED",
      run_id: "clean-run-001",
      title: "Gate Completed",
      detail: "G5 completed.",
      payload: { gate_id: "G5_REALITY", status: "PASS", decision: "ALLOW", reason_code: "REALITY_CONFIRMED" }
    },
    {
      index: 9,
      event_type: "GATE_COMPLETED",
      run_id: "clean-run-001",
      title: "Gate Completed",
      detail: "G6 completed.",
      payload: { gate_id: "G6_DECISION_SEAL", status: "PASS", decision: "ALLOW", reason_code: "DECISION_SEALED" }
    },
    {
      index: 10,
      event_type: "DECISION_MADE",
      run_id: "clean-run-001",
      title: "Decision Made",
      detail: "The deterministic decision engine folded all gate results into a final verdict.",
      payload: {
        final_decision: "ALLOW",
        status: "ALLOW",
        allow_execution: true,
        reason_codes: ["ALL_GATES_PASS"]
      }
    },
    {
      index: 11,
      event_type: "PROOF_SEALED",
      run_id: "clean-run-001",
      title: "Proof Packet Sealed",
      detail: "A deterministic proof packet was created for the clearance decision.",
      payload: {
        proof_hash: "a".repeat(64),
        final_decision: "ALLOW"
      }
    },
    {
      index: 12,
      event_type: "LEDGER_APPENDED",
      run_id: "clean-run-001",
      title: "Ledger Appended",
      detail: "The proof packet hash was appended to the in-memory SHA-256 ledger.",
      payload: {
        ledger_entry_hash: "b".repeat(64),
        previous_hash: "0".repeat(64)
      }
    },
    {
      index: 13,
      event_type: "CLEARANCE_TOKEN_ISSUED",
      run_id: "clean-run-001",
      title: "Clearance Token Issued",
      detail: "A clearance token was issued.",
      payload: {
        token_id: "tok-allow-001",
        expires_at: "2026-07-04T12:10:00Z"
      }
    },
    {
      index: 14,
      event_type: "EXECUTION_ATTEMPTED",
      run_id: "clean-run-001",
      title: "Execution Attempted",
      detail: "The Mock Bank evaluated the request.",
      payload: {
        token_id: "tok-allow-001",
        amount: 340000,
        bank_account_last4: "8821"
      }
    },
    {
      index: 15,
      event_type: "EXECUTION_ACCEPTED",
      run_id: "clean-run-001",
      title: "Execution Accepted",
      detail: "The Mock Bank accepted the payment.",
      payload: {
        reason_code: "EXECUTION_ACCEPTED",
        execution_reference: "MOCKBANK-ALLOW-001"
      }
    }
  ];

  return { run_id: "clean-run-001", events };
}

function makeProof() {
  return {
    run_id: "clean-run-001",
    proof_hash: "a".repeat(64),
    ledger_entry_hash: "b".repeat(64),
    proof_packet: {
      packet_version: "1.0",
      packet_type: "vendor_payment_clearance"
    }
  };
}

function makeVerification(verified = true) {
  return {
    run_id: "clean-run-001",
    ledger_chain_valid: verified,
    packet_entry_valid: verified,
    proof_hash: "a".repeat(64),
    ledger_entry_hash: "b".repeat(64),
    verified
  };
}

function bootstrap(configured = false) {
  mockedApiClient.getHealth.mockResolvedValue({
    status: "ok",
    service: "TOSCO",
    version: "0.1.0",
    mode: "demo"
  });
  mockedApiClient.getVultrStatus.mockResolvedValue({
    configured,
    base_url: "https://api.vultrinference.com/v1",
    model: "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
    mode: "serverless-inference",
    key_present: configured
  });
  mockedApiClient.getWorkflows.mockResolvedValue(workflows);
  mockedApiClient.getScenarios.mockResolvedValue(scenarios);
  mockedApiClient.resetDemo.mockResolvedValue({ status: "reset", runs: 0 });
  mockedApiClient.startRun.mockResolvedValue(makeRunSummary());
  mockedApiClient.getEvents.mockResolvedValue(makeTimeline());
  mockedApiClient.getProof.mockResolvedValue(makeProof());
  mockedApiClient.verifyRun.mockResolvedValue(makeVerification(true));
}

describe("vultr status and final polish", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    bootstrap(false);
  });

  it("Vultr status card never displays an API key value", async () => {
    render(<App />);

    expect(await screen.findByText("Vultr Serverless Inference")).toBeInTheDocument();
    expect(screen.getAllByText("No").length).toBeGreaterThan(0);
    expect(screen.queryByText("fake-secret-value")).not.toBeInTheDocument();
  });

  it("shows the fallback message when Vultr is not configured", async () => {
    render(<App />);

    expect(
      await screen.findByText(
        "Fallback mode active. TOSCO will use seeded extraction while preserving deterministic gates."
      )
    ).toBeInTheDocument();
  });

  it("sends use_vultr true when the toggle is enabled", async () => {
    render(<App />);

    await userEvent.click(await screen.findByLabelText("Use Vultr extraction for next run"));
    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect(mockedApiClient.startRun).toHaveBeenCalledWith("clean", true);
  });

  it("displays the Vultr fallback timeline label when the backend falls back", async () => {
    mockedApiClient.getEvents.mockResolvedValue(makeTimeline(true));

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect((await screen.findAllByText("Fallback extraction used")).length).toBeGreaterThan(0);
  });

  it("renders the final demo checklist with key proof items", async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect(await screen.findByText("Final Demo Checklist")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Agent proposed payment/i })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    expect(
      screen.getByRole("checkbox", { name: /Vultr extraction path available/i })
    ).toHaveAttribute("aria-checked", "true");
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: /Six deterministic gates executed/i })
      ).toHaveAttribute("aria-checked", "true");
    });
  });
});
