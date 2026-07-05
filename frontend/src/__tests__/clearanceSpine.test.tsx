import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildScenarioProposalRequest } from "../api/referenceProposals";
import ClearanceSpine from "../components/spine/ClearanceSpine";
import { makeContractSequence } from "../test/runFixtures";
import {
  createInitialRunState,
  runStoreReducer,
  type RunStoreState
} from "../run/store";

function proposalState(scenario: "clean" | "injection" | "forgery"): RunStoreState {
  let state = createInitialRunState();
  state = runStoreReducer(state, {
    type: "prime",
    scenario,
    proposal: buildScenarioProposalRequest(scenario),
    fallbackMode: false
  });
  state = runStoreReducer(state, {
    type: "proposalAccepted",
    intentId: `intent-${scenario}-001`
  });
  return state;
}

function completedState(scenario: "clean" | "injection" | "forgery"): RunStoreState {
  let state = proposalState(scenario);
  state = runStoreReducer(state, {
    type: "runStarted",
    runId: `run-${scenario}-001`
  });

  const decision = scenario === "clean" ? "ALLOW" : scenario === "injection" ? "BLOCK" : "FREEZE";
  return makeContractSequence(decision).reduce(
    (currentState, event) => runStoreReducer(currentState, { type: "applyEvent", event }),
    state
  );
}

describe("ClearanceSpine", () => {
  it("shows PROPOSE active before a run starts", () => {
    render(<ClearanceSpine state={proposalState("clean")} />);

    expect(screen.getByTestId("spine-row-propose")).toHaveAttribute("data-status", "active");
    expect(screen.getByTestId("spine-row-retrieve")).toHaveAttribute("data-status", "idle");
    expect(screen.queryByTestId("decision-stamp")).not.toBeInTheDocument();
  });

  it("fills through a clean run and shows a quiet CLEARED mark", () => {
    render(<ClearanceSpine state={completedState("clean")} />);

    for (const pass of Array.from({ length: 5 }, (_, index) => index + 1)) {
      expect(screen.getByTestId(`retrieve-pass-${pass}`)).toHaveAttribute("data-status", "pass");
    }

    expect(screen.getByTestId("final-decision")).toHaveTextContent("ALLOW");
    expect(screen.getByTestId("decision-stamp")).toHaveTextContent("CLEARED");
    expect(screen.getByTestId("spine-row-token")).toHaveAttribute("data-status", "pass");
    expect(screen.getByTestId("spine-row-bank")).toHaveAttribute("data-status", "pass");
    expect(screen.getByTestId("spine-row-bank")).toHaveTextContent("EXECUTED");
  });

  it("turns the spine red from the failed gate down and stamps BLOCK", () => {
    render(<ClearanceSpine state={completedState("injection")} />);

    expect(screen.getByTestId("spine-row-G2_GROUNDEDNESS")).toHaveAttribute("data-status", "fail");
    expect(screen.getByTestId("spine-segment-G2_GROUNDEDNESS")).toHaveAttribute("data-tone", "fail");
    expect(screen.getByTestId("spine-segment-G3_POLICY")).toHaveAttribute("data-tone", "fail");
    expect(screen.getByTestId("final-decision")).toHaveTextContent("BLOCK");
    expect(screen.getByTestId("decision-stamp")).toHaveTextContent("BLOCK");
  });
});
