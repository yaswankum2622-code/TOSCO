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

const scenarios = [
  {
    scenario: "clean",
    title: "Clean Payment",
    description: "Legitimate invoice, PO, and goods receipt.",
    expected_naive_agent_action: "Approve vendor payment",
    expected_tosco_decision: "ALLOW"
  },
  {
    scenario: "injection",
    title: "Prompt Injection",
    description: "Injected invoice instructions try to reroute funds.",
    expected_naive_agent_action: "Approve attacker account",
    expected_tosco_decision: "BLOCK"
  },
  {
    scenario: "forgery",
    title: "Forged Bank Change",
    description: "Documents align, but reality signals break trust.",
    expected_naive_agent_action: "Approve updated bank account",
    expected_tosco_decision: "FREEZE"
  }
];

const workflows = [
  {
    workflow_id: "vendor_payment",
    workflow_name: "Vendor Payment",
    required_evidence_types: ["invoice", "po", "grn", "vendor_master"],
    gates_to_run: ["G1_EVIDENCE", "G2_GROUNDEDNESS"],
    tools_to_call: ["policy_tool", "risk_tool"],
    execution_adapter: "sandbox"
  }
];

function makeRunSummary(finalDecision: string) {
  return {
    scenario:
      finalDecision === "BLOCK"
        ? "injection"
        : finalDecision === "FREEZE"
          ? "forgery"
          : "clean",
    run_id: `${finalDecision.toLowerCase()}-run-001`,
    final_decision: finalDecision,
    allow_execution: finalDecision === "ALLOW",
    token_issued: finalDecision === "ALLOW",
    mock_bank_status: finalDecision === "ALLOW" ? "ACCEPTED" : "REJECTED",
    mock_bank_reason_code: finalDecision === "ALLOW" ? "EXECUTION_ACCEPTED" : "MISSING_CLEARANCE_TOKEN",
    proof_hash: "a".repeat(64),
    ledger_entry_hash: "b".repeat(64),
    timeline_events_count: 9
  };
}

function mockBootstrap() {
  mockedApiClient.getHealth.mockResolvedValue({
    status: "ok",
    service: "TOSCO",
    version: "0.1.0",
    mode: "demo"
  });
  mockedApiClient.getWorkflows.mockResolvedValue(workflows);
  mockedApiClient.getScenarios.mockResolvedValue(scenarios);
}

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBootstrap();
    mockedApiClient.getEvents.mockResolvedValue({
      run_id: "run-001",
      events: [
        {
          index: 0,
          event_type: "AGENT_PROPOSED",
          run_id: "run-001",
          title: "Agent Proposed",
          detail: "The agent proposed a payment.",
          payload: {}
        }
      ]
    });
    mockedApiClient.verifyRun.mockResolvedValue({
      run_id: "run-001",
      ledger_chain_valid: true,
      packet_entry_valid: true,
      proof_hash: "a".repeat(64),
      ledger_entry_hash: "b".repeat(64),
      verified: true
    });
    mockedApiClient.resetDemo.mockResolvedValue({
      status: "reset",
      runs: 0
    });
  });

  it("renders the TOSCO header", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "TOSCO" })).toBeInTheDocument();
  });

  it("renders scenario buttons after mocked load", async () => {
    render(<App />);

    expect(await screen.findByRole("button", { name: "Run Clean Payment" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Prompt Injection" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Forged Bank Change" })).toBeInTheDocument();
  });

  it("clicking clean scenario displays backend-computed ALLOW result", async () => {
    mockedApiClient.startRun.mockResolvedValue(makeRunSummary("ALLOW"));

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("ALLOW");
  });

  it("clicking injection scenario displays backend-computed BLOCK result", async () => {
    mockedApiClient.startRun.mockResolvedValue(makeRunSummary("BLOCK"));

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Prompt Injection" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("BLOCK");
  });

  it("clicking forgery scenario displays backend-computed FREEZE result", async () => {
    mockedApiClient.startRun.mockResolvedValue(makeRunSummary("FREEZE"));

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Forged Bank Change" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("FREEZE");
  });

  it("tamper button displays verified false after mocked tamper response", async () => {
    mockedApiClient.startRun.mockResolvedValue(makeRunSummary("ALLOW"));
    mockedApiClient.tamperRun.mockResolvedValue({
      run_id: "allow-run-001",
      ledger_chain_valid: false,
      packet_entry_valid: false,
      proof_hash: "a".repeat(64),
      ledger_entry_hash: "b".repeat(64),
      verified: false
    });

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));
    await userEvent.click(await screen.findByRole("button", { name: "Tamper Demo" }));

    await waitFor(() => {
      expect(screen.getByTestId("verified-value")).toHaveTextContent("false");
    });
  });
});
