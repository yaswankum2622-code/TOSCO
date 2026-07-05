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

const workflows = [
  {
    workflow_id: "vendor_payment",
    workflow_name: "AI Vendor Payment & Bank-Change Clearance",
    required_evidence_types: ["invoice", "po", "grn", "vendor_master", "policy_pack"],
    gates_to_run: ["G1_EVIDENCE", "G2_GROUNDEDNESS", "G3_POLICY", "G4_RISK", "G5_REALITY"],
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

function bootstrap(configured = false) {
  mockedApiClient.getHealth.mockResolvedValue({
    status: "ok",
    service: "TOSCO",
    version: "0.1.0",
    mode: "demo",
    fallback_mode: true
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
  mockedApiClient.proposeIntent.mockResolvedValue({
    intent_id: "intent-clean-001",
    accepted: true
  });
  mockedApiClient.startRun.mockResolvedValue({ run_id: "run-clean-001" });
  mockedApiClient.verifyRun.mockResolvedValue({
    run_id: "run-clean-001",
    ledger_chain_valid: true,
    packet_entry_valid: true,
    proof_hash: "a".repeat(64),
    ledger_entry_hash: "b".repeat(64),
    verified: true
  });
  mockedApiClient.resetDemo.mockResolvedValue({ status: "reset", runs: 0 });
}

function emitSequence(fallbackMode = false) {
  mockRunEventsClient.start.mockImplementation((_runId, handlers) => {
    void (async () => {
      for (const event of makeContractSequence("ALLOW", { fallbackMode })) {
        await handlers.onEvent(event);
      }
      handlers.onComplete?.();
    })();
  });
}

describe("vultr status and final polish", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateRunEventsClient.mockReturnValue(mockRunEventsClient);
    bootstrap(false);
    emitSequence(false);
  });

  it("Vultr status card never displays an API key value", async () => {
    render(<App />);

    expect(await screen.findByText("Live Extraction Link")).toBeInTheDocument();
    expect(screen.getByText("Fallback rail armed")).toBeInTheDocument();
    expect(screen.queryByText("fake-secret-value")).not.toBeInTheDocument();
    expect(screen.queryByText("https://api.vultrinference.com/v1")).not.toBeInTheDocument();
  });

  it("shows the fallback message when Vultr is not configured", async () => {
    render(<App />);

    expect(
      await screen.findByText(
        "Fallback mode stays safe. TOSCO can still complete the full run without breaking the clearance path."
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
    emitSequence(true);

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect((await screen.findAllByText("Fallback extraction used")).length).toBeGreaterThan(0);
  });

  it("flips the topbar pill to fallback when the backend extraction events require it", async () => {
    emitSequence(true);

    render(<App />);

    expect(await screen.findByTestId("fallback-pill")).toHaveTextContent("LIVE SANDBOX");
    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    await waitFor(() => {
      expect(screen.getByTestId("fallback-pill")).toHaveTextContent("LIVE FALLBACK");
    });
  });
});
