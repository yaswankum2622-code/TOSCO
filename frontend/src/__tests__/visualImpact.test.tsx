import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
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
  formatCustomRunError: (error: unknown) =>
    error instanceof Error ? error.message : "Custom run failed.",
  apiClient: {
    getHealth: vi.fn(),
    getVultrStatus: vi.fn(),
    getWorkflows: vi.fn(),
    getScenarios: vi.fn(),
    proposeIntent: vi.fn(),
    startRun: vi.fn(),
    startCustomRun: vi.fn(),
    listRuns: vi.fn(),
    getRun: vi.fn(),
    attemptExecution: vi.fn(),
    verifyRun: vi.fn(),
    tamperRun: vi.fn(),
    submitReview: vi.fn(),
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

describe("visual impact pass", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateRunEventsClient.mockReturnValue(mockRunEventsClient);
    mockedApiClient.getHealth.mockResolvedValue({
      status: "ok",
      service: "TOSCO",
      version: "0.1.0",
      mode: "demo",
      fallback_mode: false
    });
    mockedApiClient.getVultrStatus.mockResolvedValue({
      configured: true,
      base_url: "https://api.vultrinference.com/v1",
      model: "test-model",
      mode: "serverless-inference",
      key_present: true
    });
    mockedApiClient.getWorkflows.mockResolvedValue(workflows);
    mockedApiClient.getScenarios.mockResolvedValue(scenarios);
    mockedApiClient.proposeIntent.mockResolvedValue({ intent_id: "intent-clean-001", accepted: true });
    mockedApiClient.startRun.mockResolvedValue({ run_id: "run-clean-001" });
    mockedApiClient.attemptExecution.mockResolvedValue({ executed: true, reason: "CLEARED" });
    mockedApiClient.resetDemo.mockResolvedValue({ status: "reset", runs: 0 });
  });

  it("uses SkyGlass Enterprise palette tokens", () => {
    const themeCss = readFileSync(resolve(process.cwd(), "src/theme.css"), "utf8");
    const appCss = readFileSync(resolve(process.cwd(), "src/App.css"), "utf8");

    expect(themeCss).toContain("--bg-main: #05070a");
    expect(themeCss).toContain("--allow: #22c55e");
    expect(themeCss).toContain("--block: #ef4444");
    expect(themeCss).toContain("--accent: #6ec6ff");
    expect(themeCss).toContain("--proof: #a78bfa");
    expect(themeCss).toContain("--ledger: #2dd4bf");
    expect(appCss).toContain("@keyframes decision-hero-glow-allow");
    expect(appCss).toContain("@keyframes decision-hero-glow-deny");
    expect(appCss).toContain(".proof-packet-viewer");
    expect(appCss).toContain("backdrop-filter: blur(var(--glass-blur))");
  });

  it("surfaces decision card and counterfactual amount as the dominant stack on block", async () => {
    emitSequence("BLOCK");

    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Run Prompt Injection" }));

    const decisionCard = await screen.findByTestId("decision-card");
    expect(decisionCard).toHaveClass("right-card--decision");
    expect(decisionCard).toHaveClass("right-card--deny");
    expect(decisionCard).toHaveTextContent("BLOCK");
    expect(screen.getByTestId("counterfactual-amount")).toHaveTextContent("$340,000");
  });

  it("surfaces allow decision and zero exposure on clean run", async () => {
    emitSequence("ALLOW");

    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    const decisionCard = await screen.findByTestId("decision-card");
    expect(decisionCard).toHaveClass("right-card--allow");
    expect(screen.getByTestId("counterfactual-amount")).toHaveTextContent("$0 exposure");
  });
});
