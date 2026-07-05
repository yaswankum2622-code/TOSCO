import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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
    intent_id: "intent-demo-001",
    accepted: true
  });
  mockedApiClient.startRun.mockImplementation(async (scenario: string) => ({
    run_id: `run-${scenario}-001`
  }));
  mockedApiClient.attemptExecution.mockResolvedValue({
    executed: true,
    reason: "CLEARED"
  });
  mockedApiClient.verifyRun.mockResolvedValue(verifiedResponse);
  mockedApiClient.tamperRun.mockResolvedValue(tamperedResponse);
  mockedApiClient.resetDemo.mockResolvedValue({ status: "reset", runs: 0 });
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

describe("ui polish", () => {
  const themeCss = readFileSync(resolve(process.cwd(), "src/theme.css"), "utf8");
  const appCss = readFileSync(resolve(process.cwd(), "src/App.css"), "utf8");

  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateRunEventsClient.mockReturnValue(mockRunEventsClient);
    bootstrap();
  });

  it("renders the premium terminal hero and removes unfinished placeholder labels", async () => {
    render(<App />);

    expect(await screen.findByTestId("console-grid")).toBeInTheDocument();
    expect(screen.getByText("Agents propose. TOSCO clears. Execution obeys. Audit proves.")).toBeInTheDocument();
    expect(
      screen.getByText("Trust-Orchestrated Settlement & Control OS", { exact: false })
    ).toBeInTheDocument();
    expect(screen.queryByText("$3.05B lost to BEC last year")).not.toBeInTheDocument();
    expect(screen.getByText("Trace every proposal")).toBeInTheDocument();
    expect(screen.getByText("Gate deterministically")).toBeInTheDocument();
    expect(screen.getByText("Seal every outcome")).toBeInTheDocument();
    expect(screen.queryByText("Final Demo Checklist")).not.toBeInTheDocument();
    expect(screen.queryByText("Left Column")).not.toBeInTheDocument();
    expect(screen.queryByText("Center Console")).not.toBeInTheDocument();
    expect(screen.queryByText("Right Stack")).not.toBeInTheDocument();
  });

  it("keeps the three-column desktop grid, mobile stack, and updated palette contract", () => {
    expect(themeCss).toContain("grid-template-columns: 300px minmax(0, 1fr) 380px;");
    expect(themeCss).toContain("--bg: #000000;");
    expect(themeCss).toContain("--panel: #0a0c10;");
    expect(themeCss).toContain("--accent: #3b82f6;");
    expect(themeCss).not.toContain("--cyan:");
    expect(themeCss).not.toContain("--pink:");
    expect(themeCss).not.toContain("139, 92, 246");
    expect(themeCss).toContain("@media (max-width: 900px)");
    expect(themeCss).toContain("grid-template-columns: 1fr;");
    expect(appCss).toContain("background: var(--panel);");
  });

  it("after clean run shows the event-bound allow outcome stack", async () => {
    emitSequence("ALLOW");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Clean Payment" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("ALLOW");
    expect(screen.queryByTestId("naive-agent-strip")).not.toBeInTheDocument();
    expect(screen.getByTestId("decision-card")).toHaveTextContent("ALLOW");
    expect(screen.getByTestId("token-card")).toHaveTextContent("Token issued");
    expect(screen.getByTestId("token-value")).toHaveTextContent("tok-clean-001");
    expect(screen.getByTestId("mock-bank-execution-card")).toHaveTextContent("Executed - CLEARED");
    expect(screen.queryByTestId("sentinel-card")).not.toBeInTheDocument();
    expect(screen.getByTestId("proof-packet-viewer")).toBeInTheDocument();
    expect(screen.getByTestId("hash-verifier")).toBeInTheDocument();
    expect(screen.getByTestId("proof-chain-hash")).toHaveTextContent("a".repeat(64));
    expect(screen.getAllByText("CLEARED").length).toBeGreaterThan(0);
    expect(screen.getAllByText("aaaaaaaaaaaa...aaaaaaaaaa").length).toBeGreaterThan(0);

    await userEvent.click(screen.getByRole("button", { name: "Attempt execution" }));
    expect(mockedApiClient.attemptExecution).toHaveBeenCalledWith({
      run_id: "run-clean-001",
      token: expect.stringContaining("\"token_id\":\"tok-clean-001\""),
      vendor_id: "VEND-ACME-001",
      amount: 340000
    });
  });

  it("after injection run shows the naive strip and blocked outcome stack", async () => {
    emitSequence("BLOCK");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Prompt Injection" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("BLOCK");
    expect(screen.getByTestId("naive-agent-strip")).toHaveTextContent("Naive agent");
    expect(screen.getByTestId("decision-card")).toHaveTextContent("BLOCK");
    expect(screen.getByTestId("token-card")).toHaveTextContent("No clearance token issued");
    expect(screen.getByTestId("mock-bank-execution-card")).toHaveTextContent("Rejected - NO_TOKEN");
    expect(screen.getByTestId("counterfactual-strip")).toBeInTheDocument();
    expect(screen.getByTestId("counterfactual-amount")).toHaveTextContent("$340,000");
    expect(screen.getByTestId("sentinel-card")).toHaveTextContent("BANK_ACCOUNT_MISMATCH");
    expect(screen.getByTestId("terminal-vignette-flash")).toBeInTheDocument();
    expect(screen.getAllByText("BANK_ACCOUNT_MISMATCH").length).toBeGreaterThan(0);
    expect(screen.getAllByText("NO_TOKEN").length).toBeGreaterThan(0);
  });

  it("after forgery run shows freeze and the sentinel reality mismatch", async () => {
    emitSequence("FREEZE");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Forged Bank Change" }));

    expect(await screen.findByTestId("final-decision")).toHaveTextContent("FREEZE");
    expect(screen.getByTestId("decision-card")).toHaveTextContent("FREEZE");
    expect(screen.getByTestId("counterfactual-amount")).toHaveTextContent("$340,000");
    expect(screen.getByTestId("sentinel-card")).toHaveTextContent("REALITY_OWNER_MISMATCH");
    expect(screen.getAllByText("REALITY_OWNER_MISMATCH_FREEZE").length).toBeGreaterThan(0);
    expect(screen.getByText("G5 REALITY")).toBeInTheDocument();
  });

  it("tamper demo flips the hash verifier to failed and shows the tampered field", async () => {
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

  it("does not display raw injection document body from backend-driven state", async () => {
    emitSequence("BLOCK");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Run Prompt Injection" }));

    await waitFor(() => {
      expect(screen.queryByText(/IGNORE PREVIOUS INSTRUCTIONS/i)).not.toBeInTheDocument();
    });
  });
});
