import { afterEach, describe, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";

import { createRunEventsClient } from "../api/events";
import { buildScenarioProposalRequest } from "../api/referenceProposals";
import type { ContractRunEvent, RunSnapshotResponse } from "../api/types";
import { makeContractSequence, makeSnapshot } from "../test/runFixtures";
import {
  createInitialRunState,
  runStoreReducer,
  type RunStoreState
} from "../run/store";

function primeState(scenario: "clean" | "injection" | "forgery"): RunStoreState {
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
  state = runStoreReducer(state, {
    type: "runStarted",
    runId: `run-${scenario}-001`
  });
  return state;
}

function applySequence(
  scenario: "clean" | "injection" | "forgery",
  events: ContractRunEvent[]
): RunStoreState {
  return events.reduce(
    (state, event) => runStoreReducer(state, { type: "applyEvent", event }),
    primeState(scenario)
  );
}

function comparableState(state: RunStoreState) {
  return {
    workflow: state.workflow,
    fallbackMode: state.fallbackMode,
    streamMode: state.streamMode,
    stations: state.stations.map((station) => ({
      id: station.id,
      status: station.status,
      detail: station.detail
    })),
    gates: state.gates.map((gate) => ({
      id: gate.id,
      status: gate.status,
      reasonCode: gate.reasonCode
    })),
    decision: state.decision,
    token: state.token
      ? {
          issued: state.token.issued,
          tokenShort: state.token.tokenShort,
          exp: state.token.exp
        }
      : null,
    bank: state.bank,
    proof: state.proof,
    sentinel: state.sentinel
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("run events store", () => {
  it("feeding a recorded clean sequence resolves every station and ends at ALLOW", () => {
    const state = applySequence("clean", makeContractSequence("ALLOW"));

    expect(state.stations.every((station) => station.status === "pass" || station.status === "fail")).toBe(true);
    expect(state.decision?.value).toBe("ALLOW");
    expect(state.bank).toEqual({ executed: true, reason: "CLEARED" });
  });

  it("feeding a forgery sequence yields G5 fail and decision FREEZE purely from events", () => {
    const state = applySequence("forgery", makeContractSequence("FREEZE"));
    const realityGate = state.gates.find((gate) => gate.id === "G5_REALITY");

    expect(realityGate?.status).toBe("FAIL");
    expect(realityGate?.reasonCode).toBe("REALITY_OWNER_MISMATCH_FREEZE");
    expect(state.decision?.value).toBe("FREEZE");
  });

  it("with EventSource forced to error, poll fallback produces the identical final state", async () => {
    vi.stubGlobal("EventSource", undefined);

    const snapshot = makeSnapshot("ALLOW");
    const expected = applySequence("clean", makeContractSequence("ALLOW"));
    const client = createRunEventsClient({
      getSnapshot: async () => snapshot,
      attemptExecution: async () => ({
        executed: true,
        reason: "CLEARED"
      })
    });

    let state = primeState("clean");
    let completed = false;

    client.start(snapshot.run_id, {
      onEvent: async (event) => {
        state = runStoreReducer(state, { type: "applyEvent", event });
      },
      onComplete: () => {
        completed = true;
      },
      buildExecutionRequest: (currentSnapshot: RunSnapshotResponse | null) => {
        const source = currentSnapshot ?? snapshot;
        return {
          run_id: source.run_id,
          token: source.clearance_token,
          vendor_id: source.intent?.action.vendor_id ?? "VEND-ACME-001",
          amount: source.intent?.action.amount ?? 340000
        };
      }
    });

    await waitFor(() => {
      expect(completed).toBe(true);
    });

    expect(comparableState(state)).toEqual(comparableState(expected));
  });

  it("derives counterfactual exposure from the backend decision", () => {
    const allowState = applySequence("clean", makeContractSequence("ALLOW"));
    expect(allowState.counterfactual?.loss).toBe("$0 exposure — executed safely");

    const blockState = applySequence("injection", makeContractSequence("BLOCK"));
    expect(blockState.counterfactual?.loss).toContain("$340,000");
  });

  it("decision stays null until DECISION_MADE is applied", () => {
    const events = makeContractSequence("ALLOW");
    const decisionIndex = events.findIndex((event) => event.event === "DECISION_MADE");
    let state = primeState("clean");

    for (const event of events.slice(0, decisionIndex)) {
      state = runStoreReducer(state, { type: "applyEvent", event });
      expect(state.decision).toBeNull();
    }

    state = runStoreReducer(state, { type: "applyEvent", event: events[decisionIndex] });
    expect(state.decision?.value).toBe("ALLOW");
  });

  it("uses the backend snapshot token for live execution when the local state is not caught up yet", async () => {
    const events = makeContractSequence("ALLOW").filter(
      (event) => event.event === "TOKEN_ISSUED" || event.event === "EXECUTION_ATTEMPTED"
    );
    const snapshot = makeSnapshot("ALLOW");
    const executionRequests: Array<{ token: string | null }> = [];
    const source = {
      onmessage: null as ((event: MessageEvent<string>) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      close: vi.fn()
    };
    const client = createRunEventsClient({
      createEventSource: () => source,
      getSnapshot: async () => snapshot,
      attemptExecution: async (payload) => {
        executionRequests.push({ token: payload.token });
        return {
          executed: true,
          reason: "CLEARED"
        };
      }
    });

    const seenEvents: ContractRunEvent[] = [];
    client.start(snapshot.run_id, {
      onEvent: async (event) => {
        seenEvents.push(event);
      },
      buildExecutionRequest: (currentSnapshot) => {
        if (currentSnapshot === null) {
          return {
            run_id: snapshot.run_id,
            token: null,
            vendor_id: "VEND-ACME-001",
            amount: 340000
          };
        }

        return {
          run_id: currentSnapshot.run_id,
          token: currentSnapshot.clearance_token,
          vendor_id: currentSnapshot.intent?.action.vendor_id ?? "VEND-ACME-001",
          amount: currentSnapshot.intent?.action.amount ?? 340000
        };
      }
    });

    for (const event of events) {
      await source.onmessage?.({
        data: JSON.stringify(event)
      } as MessageEvent<string>);
    }

    await waitFor(() => {
      expect(executionRequests).toHaveLength(1);
    });

    expect(executionRequests[0]?.token).toBe(snapshot.clearance_token);
    expect(seenEvents.at(-1)?.event).toBe("EXECUTION_ATTEMPTED");
    expect(seenEvents.at(-1)?.data["executed"]).toBe(true);
  });

  it("does not fall back to polling after the terminal SSE event has already been seen", async () => {
    const snapshot = makeSnapshot("ALLOW");
    let snapshotCalls = 0;
    let executionCalls = 0;
    const source = {
      onmessage: null as ((event: MessageEvent<string>) => void) | null,
      onerror: null as ((event: Event) => void) | null,
      close: vi.fn()
    };
    const client = createRunEventsClient({
      createEventSource: () => source,
      getSnapshot: async () => {
        snapshotCalls += 1;
        return snapshot;
      },
      attemptExecution: async () => {
        executionCalls += 1;
        await Promise.resolve();
        return {
          executed: true,
          reason: "CLEARED"
        };
      }
    });

    client.start(snapshot.run_id, {
      onEvent: async () => undefined,
      buildExecutionRequest: () => ({
        run_id: snapshot.run_id,
        token: null,
        vendor_id: "VEND-ACME-001",
        amount: 340000
      })
    });

    source.onmessage?.({
      data: JSON.stringify(
        makeContractSequence("ALLOW").find((event) => event.event === "EXECUTION_ATTEMPTED")
      )
    } as MessageEvent<string>);
    source.onerror?.(new Event("error"));

    await waitFor(() => {
      expect(executionCalls).toBe(1);
    });

    await new Promise((resolve) => setTimeout(resolve, 25));

    expect(snapshotCalls).toBe(1);
    expect(executionCalls).toBe(1);
  });
});
