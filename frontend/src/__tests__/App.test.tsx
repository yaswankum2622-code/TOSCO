import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { apiClient } from "../api/client";
import { createRunEventsClient } from "../api/events";
import { makeContractSequence } from "../test/runFixtures";

const mockRunEventsClient = {
  start: vi.fn(),
  stop: vi.fn()
};

vi.mock("../api/events", () => ({
  createRunEventsClient: vi.fn(() => mockRunEventsClient)
}));

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
    proposeIntent: vi.fn(),
    startRun: vi.fn(),
    listRuns: vi.fn(),
    getRun: vi.fn(),
    attemptExecution: vi.fn(),
    verifyRun: vi.fn(),
    tamperRun: vi.fn(),
    resetDemo: vi.fn()
  }
}));

const mockedApiClient = vi.mocked(apiClient);
const mockedCreateRunEventsClient = vi.mocked(createRunEventsClient);

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
    required_evidence_types: ["invoice", "po", "grn", "vendor_master", "policy_pack"],
    gates_to_run: ["G1_EVIDENCE", "G2_GROUNDEDNESS", "G3_POLICY", "G4_RISK", "G5_REALITY"],
    tools_to_call: ["policy_tool", "risk_tool"],
    execution_adapter: "sandbox"
  }
];

const verifiedResponse = {
  run_id: "run-clean-001",
  ledger_chain_valid: true,
  packet_entry_valid: true,
  proof_hash: "a".repeat(64),
  ledger_entry_hash: "b".repeat(64),
  chain_head: "b".repeat(64),
  verified: true
};

const tamperedResponse = {
  run_id: "run-clean-001",
  ledger_chain_valid: false,
  packet_entry_valid: false,
  proof_hash: "a".repeat(64),
  ledger_entry_hash: "b".repeat(64),
  chain_head: "b".repeat(64),
  verified: false,
  tampered_field: "packet_hash",
  verify_now: false
};

function runIdForScenario(scenario: string): string {
  return `run-${scenario}-001`;
}

function bootstrap() {
  mockedApiClient.getHealth.mockResolvedValue({
    status: "ok",
    service: "TOSCO",
    version: "0.1.0",
    mode: "demo",
    fallback_mode: true
  });
  mockedApiClient.getVultrStatus.mockResolvedValue({
    configured: false,
    base_url: "https://api.vultrinference.com/v1",
    model: "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
    mode: "serverless-inference",
    key_present: false
  });
  mockedApiClient.getWorkflows.mockResolvedValue(workflows);
  mockedApiClient.getScenarios.mockResolvedValue(scenarios);
  mockedApiClient.proposeIntent.mockResolvedValue({
    intent_id: "intent-clean-001",
    accepted: true
  });
  mockedApiClient.startRun.mockImplementation(async (scenario: string) => ({
    run_id: runIdForScenario(scenario)
  }));
  mockedApiClient.verifyRun.mockResolvedValue(verifiedResponse);
  mockedApiClient.tamperRun.mockResolvedValue(tamperedResponse);
  mockedApiClient.resetDemo.mockResolvedValue({
    status: "reset",
    runs: 0
  });
}

function emitSequence(decision: "ALLOW" | "BLOCK" | "FREEZE") {
  mockRunEventsClient.start.mockImplementation((_runId, handlers) => {
    void (async () => {
      for (const event of makeContractSequence(decision)) {
        await handlers.onEvent(event);
      }
      handlers.onComplete?.();
    })();
  });
}

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateRunEventsClient.mockReturnValue(mockRunEventsClient);
    bootstrap();
  });

  it("renders the clearance console shell with a sandbox pill by default", async () => {
    render(<App />);

    await screen.findByRole("button", { name: "Run Clean Payment" });

    expect(screen.getByTestId("console-topbar")).toBeInTheDocument();
    expect(screen.getByTestId("console-grid")).toBeInTheDocument();
    expect(screen.getByTestId("left-column")).toBeInTheDocument();
    expect(screen.getByTestId("center-console")).toBeInTheDocument();
    expect(screen.getByTestId("right-stack")).toBeInTheDocument();
    expect(screen.getByTestId("fallback-pill")).toHaveTextContent("LIVE SANDBOX");
    expect(screen.getByTestId("settlement-hero")).toHaveAttribute("data-collapsed", "false");
    expect(screen.getByText("Agents propose. TOSCO clears. Execution obeys. Audit proves.")).toBeInTheDocument();
    expect(screen.getByText("Vendor Payment")).toBeInTheDocument();
  });

  it("renders scenario buttons after mocked load", async () => {
    render(<App />);

    expect(await screen.findByRole("button", { name: "Run Clean Payment" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Prompt Injection" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Forged Bank Change" })).toBeInTheDocument();
  });

  it("clicking clean scenario displays backend event ALLOW result", async () => {
    emitSequence("ALLOW");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("ALLOW");
  });

  it("collapses the hero once a run starts", async () => {
    emitSequence("ALLOW");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    await waitFor(() => {
      expect(screen.getByTestId("settlement-hero")).toHaveAttribute("data-collapsed", "true");
    });
  });

  it("clicking injection scenario displays backend event BLOCK result", async () => {
    emitSequence("BLOCK");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Prompt Injection" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("BLOCK");
  });

  it("clicking forgery scenario displays backend event FREEZE result", async () => {
    emitSequence("FREEZE");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Forged Bank Change" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("FREEZE");
  });

  it("keeps hash verifier controls hidden before proof is sealed", async () => {
    render(<App />);

    await screen.findByRole("button", { name: "Run Clean Payment" });

    expect(screen.queryByTestId("hash-verifier")).not.toBeInTheDocument();
  });

  it("verify chain displays a verified result after a sealed run", async () => {
    emitSequence("ALLOW");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));
    await userEvent.click(await screen.findByRole("button", { name: "Verify chain" }));

    await waitFor(() => {
      expect(screen.getByTestId("hash-verifier-result")).toHaveTextContent("VERIFIED");
    });
    expect(screen.getByTestId("hash-verifier-status")).toHaveTextContent("VERIFIED");
  });

  it("tamper auto re-verifies and keeps the tampered field note", async () => {
    emitSequence("ALLOW");
    mockedApiClient.verifyRun.mockResolvedValueOnce(verifiedResponse).mockResolvedValueOnce(tamperedResponse);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));
    await userEvent.click(await screen.findByRole("button", { name: "Verify chain" }));
    await userEvent.click(await screen.findByRole("button", { name: "Tamper a row" }));

    await waitFor(() => {
      expect(screen.getByTestId("hash-verifier-result")).toHaveTextContent("FAILED");
    });
    expect(screen.getByTestId("hash-verifier-tampered-field")).toHaveTextContent("packet_hash");
  });
});
