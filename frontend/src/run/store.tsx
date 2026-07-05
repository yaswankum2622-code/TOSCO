import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type PropsWithChildren
} from "react";

import type {
  AgentProposeRequest,
  ContractRunEvent,
  EventTimelineResponse,
  OrchestratorEvent,
  RunSummaryResponse,
  VerifyRunResponse
} from "../api/types";
import { formatMoney, shortHash } from "../utils/format";

export type StationStatus = "idle" | "active" | "pass" | "fail";
export type GateStatus = "idle" | "active" | "PASS" | "WARN" | "FAIL";
export type StreamMode = "idle" | "sse" | "poll";

export interface RunStation {
  id: string;
  label: string;
  status: StationStatus;
  detail: string;
}

export interface RunGateState {
  id: string;
  status: GateStatus;
  reasonCode: string | null;
  humanReason: string | null;
}

export interface RunDecisionState {
  value: string;
  humanReason: string;
}

export interface RunTokenState {
  issued: boolean;
  tokenShort: string | null;
  exp: string | null;
  raw: string | null;
}

export interface RunBankState {
  executed: boolean;
  reason: string;
}

export interface RunProofState {
  sealed: boolean;
  chainHash: string | null;
}

export interface RunVerificationState {
  verified: boolean;
  chainHead: string;
  proofHash: string;
  ledgerEntryHash: string;
  ledgerChainValid: boolean;
  packetEntryValid: boolean;
  tamperedField: string | null;
  brokenRecordIndex: number | null;
}

export interface RunReviewState {
  required: boolean;
  reason: string;
  reviewerId: string;
  resolved: boolean;
  action: string | null;
}

export interface RunCounterfactualState {
  loss: string;
  narrative: string;
}

export interface RunProposalState {
  request: AgentProposeRequest;
  intentId: string | null;
  accepted: boolean;
}

export interface RunStoreState {
  runId: string | null;
  scenario: string | null;
  workflow: string | null;
  fallbackMode: boolean;
  streamMode: StreamMode;
  pending: boolean;
  proposal: RunProposalState | null;
  stations: RunStation[];
  gates: RunGateState[];
  decision: RunDecisionState | null;
  token: RunTokenState | null;
  bank: RunBankState | null;
  proof: RunProofState | null;
  verification: RunVerificationState | null;
  sentinel: string | null;
  counterfactual: RunCounterfactualState | null;
  review: RunReviewState | null;
  events: ContractRunEvent[];
  error: string | null;
}

type RunStoreAction =
  | { type: "reset" }
  | {
      type: "prime";
      scenario: string;
      proposal: AgentProposeRequest;
      fallbackMode: boolean;
    }
  | { type: "proposalAccepted"; intentId: string }
  | { type: "runStarted"; runId: string }
  | { type: "streamMode"; mode: StreamMode }
  | { type: "applyEvent"; event: ContractRunEvent }
  | { type: "verificationUpdated"; verification: VerifyRunResponse; tamperedField?: string | null }
  | { type: "setReviewReviewerId"; reviewerId: string }
  | { type: "setError"; message: string | null }
  | { type: "markComplete" };

const STATION_DEFS = [
  { id: "plan", label: "Plan" },
  { id: "evidence", label: "Evidence" },
  { id: "extraction", label: "Extraction" },
  { id: "tools", label: "Tools" },
  { id: "gates", label: "Gates" },
  { id: "decision", label: "Decision" },
  { id: "review", label: "Review" },
  { id: "token", label: "Token" },
  { id: "proof", label: "Proof" },
  { id: "bank", label: "Bank" }
] as const;

const GATE_IDS = [
  "G1_EVIDENCE",
  "G2_GROUNDEDNESS",
  "G3_POLICY",
  "G4_RISK",
  "G5_REALITY"
] as const;

function buildCounterfactualFromDecision(
  decision: string,
  amount: number
): RunCounterfactualState {
  if (decision === "ALLOW") {
    return {
      loss: "$0 exposure — executed safely",
      narrative: "TOSCO cleared the payment and sealed the execution path to the backend verdict."
    };
  }

  const formattedAmount = formatMoney(amount);
  return {
    loss: `Without TOSCO, ${formattedAmount} would have moved without clearance.`,
    narrative:
      decision === "FREEZE"
        ? "TOSCO froze the run when reality checks contradicted the seemingly consistent paperwork."
        : "TOSCO blocked the payment before any token-backed execution could clear."
  };
}

function buildInitialStations(): RunStation[] {
  return STATION_DEFS.map((station) => ({
    ...station,
    status: "idle",
    detail: "idle"
  }));
}

function buildInitialGates(): RunGateState[] {
  return GATE_IDS.map((id) => ({
    id,
    status: "idle",
    reasonCode: null,
    humanReason: null
  }));
}

export function createInitialRunState(): RunStoreState {
  return {
    runId: null,
    scenario: null,
    workflow: null,
    fallbackMode: false,
    streamMode: "idle",
    pending: false,
    proposal: null,
    stations: buildInitialStations(),
    gates: buildInitialGates(),
    decision: null,
    token: null,
    bank: null,
    proof: null,
    verification: null,
    sentinel: null,
    counterfactual: null,
    review: null,
    events: [],
    error: null
  };
}

function updateStation(
  stations: RunStation[],
  id: RunStation["id"],
  status: StationStatus,
  detail: string
): RunStation[] {
  return stations.map((station) =>
    station.id === id
      ? {
          ...station,
          status,
          detail
        }
      : station
  );
}

function updateGateState(
  gates: RunGateState[],
  gateId: string,
  update: Partial<RunGateState>
): RunGateState[] {
  return gates.map((gate) =>
    gate.id === gateId
      ? {
          ...gate,
          ...update
        }
      : gate
  );
}

function stringValue(data: Record<string, unknown>, key: string): string | null {
  const value = data[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(data: Record<string, unknown>, key: string): number | null {
  const value = data[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function booleanValue(data: Record<string, unknown>, key: string): boolean | null {
  const value = data[key];
  return typeof value === "boolean" ? value : null;
}

function stringArrayValue(data: Record<string, unknown>, key: string): string[] {
  const value = data[key];
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string");
}

function summarizeReasonCodes(reasonCodes: string[]): string {
  return reasonCodes.join(" | ") || "Awaiting backend decision";
}

function stationStatusFromGateStatuses(gates: RunGateState[]): StationStatus {
  if (gates.some((gate) => gate.status === "FAIL" || gate.status === "WARN")) {
    return "fail";
  }
  if (gates.every((gate) => gate.status === "PASS")) {
    return "pass";
  }
  return "active";
}

function detailForGateStatuses(gates: RunGateState[]): string {
  const completed = gates.filter((gate) => gate.status !== "idle" && gate.status !== "active").length;
  const failed = gates.find((gate) => gate.status === "FAIL" || gate.status === "WARN");
  if (failed?.reasonCode) {
    return failed.reasonCode;
  }
  return `${completed}/${gates.length} resolved`;
}

function reduceContractEvent(state: RunStoreState, event: ContractRunEvent): RunStoreState {
  const data = event.data;
  let nextState: RunStoreState = {
    ...state,
    runId: event.run_id || state.runId,
    events: [...state.events, event]
  };

  switch (event.event) {
    case "PLAN_STARTED": {
      const workflowId = stringValue(data, "workflow_id");
      const planStations = updateStation(nextState.stations, "plan", "pass", workflowId ?? "planned");
      nextState = {
        ...nextState,
        workflow: workflowId ?? nextState.workflow,
        stations: updateStation(planStations, "evidence", "active", "0/5 seeded")
      };
      return nextState;
    }
    case "EVIDENCE_RETRIEVED": {
      const retrievalPass = numberValue(data, "retrieval_pass") ?? 0;
      const totalPasses = numberValue(data, "total_passes") ?? Math.max(retrievalPass, 1);
      const docId = stringValue(data, "doc_id");
      const status: StationStatus = retrievalPass >= totalPasses ? "pass" : "active";
      nextState = {
        ...nextState,
        stations: updateStation(
          nextState.stations,
          "evidence",
          status,
          `${retrievalPass}/${totalPasses}${docId ? ` ${docId}` : ""}`
        )
      };
      if (status === "pass") {
        nextState = {
          ...nextState,
          stations: updateStation(nextState.stations, "extraction", "active", "awaiting seal")
        };
      }
      return nextState;
    }
    case "EXTRACTION_STARTED": {
      const fallbackMode = booleanValue(data, "fallback_mode");
      nextState = {
        ...nextState,
        fallbackMode: fallbackMode ?? nextState.fallbackMode,
        stations: updateStation(
          nextState.stations,
          "extraction",
          "active",
          stringValue(data, "extractor") ?? "extracting"
        )
      };
      return nextState;
    }
    case "EXTRACTION_SEALED": {
      const fallbackMode = booleanValue(data, "fallback_mode");
      const extractionHash = stringValue(data, "extraction_hash");
      nextState = {
        ...nextState,
        fallbackMode: fallbackMode ?? nextState.fallbackMode,
        stations: updateStation(
          nextState.stations,
          "extraction",
          "pass",
          extractionHash ? shortHash(extractionHash, 10, 8) : "sealed"
        )
      };
      nextState = {
        ...nextState,
        stations: updateStation(nextState.stations, "tools", "active", "awaiting tool calls")
      };
      return nextState;
    }
    case "TOOL_CALLED": {
      nextState = {
        ...nextState,
        stations: updateStation(
          nextState.stations,
          "tools",
          "active",
          stringValue(data, "tool_id") ?? "tool_called"
        )
      };
      return nextState;
    }
    case "GATE_STARTED": {
      const gateId = stringValue(data, "gate_id");
      const toolStations = updateStation(nextState.stations, "tools", "pass", "tool pass complete");
      nextState = {
        ...nextState,
        stations: updateStation(toolStations, "gates", "active", gateId ?? "running")
      };
      if (gateId) {
        nextState = {
          ...nextState,
          gates: updateGateState(nextState.gates, gateId, { status: "active" })
        };
      }
      return nextState;
    }
    case "GATE_COMPLETED": {
      const gateId = stringValue(data, "gate_id");
      const status = stringValue(data, "status");
      const reasonCode = stringValue(data, "reason_code");
      const humanReason = stringValue(data, "human_reason");
      if (gateId && status) {
        nextState = {
          ...nextState,
          gates: updateGateState(nextState.gates, gateId, {
            status: status as GateStatus,
            reasonCode,
            humanReason
          })
        };
        nextState = {
          ...nextState,
          stations: updateStation(
            nextState.stations,
            "gates",
            stationStatusFromGateStatuses(nextState.gates),
            detailForGateStatuses(nextState.gates)
          )
        };
      }
      return nextState;
    }
    case "DECISION_MADE": {
      const decisionValue = stringValue(data, "final_decision");
      const reasonCodes = stringArrayValue(data, "reason_codes");
      if (decisionValue) {
        const needsReview = decisionValue === "ESCALATE";
        const decisionStations = updateStation(
          nextState.stations,
          "decision",
          decisionValue === "ALLOW" ? "pass" : "fail",
          decisionValue
        );
        const reviewStations = needsReview
          ? updateStation(decisionStations, "review", "active", "awaiting reviewer")
          : updateStation(decisionStations, "review", "pass", "not required");
        const tokenStations = updateStation(
          reviewStations,
          "token",
          needsReview ? "idle" : decisionValue === "ALLOW" ? "active" : "fail",
          needsReview ? "paused for review" : decisionValue === "ALLOW" ? "awaiting token" : "not issued"
        );
        nextState = {
          ...nextState,
          decision: {
            value: decisionValue,
            humanReason: summarizeReasonCodes(reasonCodes)
          },
          sentinel: decisionValue === "ALLOW" ? null : reasonCodes[0] ?? nextState.sentinel,
          counterfactual: buildCounterfactualFromDecision(
            decisionValue,
            nextState.proposal?.request.action.amount ?? 0
          ),
          stations: updateStation(tokenStations, "proof", "idle", needsReview ? "paused" : "awaiting proof seal")
        };
      }
      return nextState;
    }
    case "REVIEW_REQUIRED": {
      const reviewReason = stringValue(data, "review_reason") ?? "Human review required.";
      nextState = {
        ...nextState,
        review: {
          required: true,
          reason: reviewReason,
          reviewerId: nextState.review?.reviewerId ?? "",
          resolved: false,
          action: null
        },
        pending: true,
        stations: updateStation(
          updateStation(nextState.stations, "review", "active", "awaiting reviewer"),
          "token",
          "idle",
          "paused for review"
        )
      };
      return nextState;
    }
    case "REVIEW_COMPLETED": {
      const action = stringValue(data, "action");
      const reviewerId = stringValue(data, "reviewer_id") ?? nextState.review?.reviewerId ?? "";
      nextState = {
        ...nextState,
        review: {
          required: true,
          reason: nextState.review?.reason ?? "Human review required.",
          reviewerId,
          resolved: true,
          action
        },
        stations: updateStation(nextState.stations, "review", action === "APPROVED" ? "pass" : "fail", action ?? "completed")
      };
      if (action === "APPROVED") {
        nextState = {
          ...nextState,
          stations: updateStation(nextState.stations, "token", "active", "awaiting token")
        };
      }
      return nextState;
    }
    case "TOKEN_ISSUED": {
      const tokenRaw = stringValue(data, "token");
      const tokenId = stringValue(data, "token_id");
      const expiresAt = stringValue(data, "expires_at");
      nextState = {
        ...nextState,
        token: {
          issued: true,
          tokenShort: tokenId ?? (tokenRaw ? shortHash(tokenRaw, 12, 10) : null),
          exp: expiresAt,
          raw: tokenRaw
        },
        stations: updateStation(
          nextState.stations,
          "token",
          "pass",
          tokenId ?? "issued"
        )
      };
      return nextState;
    }
    case "PROOF_SEALED": {
      const proofHash = stringValue(data, "proof_hash");
      const proofStations = updateStation(
        nextState.stations,
        "proof",
        "pass",
        proofHash ? shortHash(proofHash, 12, 10) : "sealed"
      );
      nextState = {
        ...nextState,
        proof: {
          sealed: true,
          chainHash: proofHash
        },
        stations: updateStation(proofStations, "bank", "active", "awaiting execution")
      };
      return nextState;
    }
    case "EXECUTION_ATTEMPTED": {
      const executed = booleanValue(data, "executed");
      const reason = stringValue(data, "reason");
      if (executed === null || reason === null) {
        nextState = {
          ...nextState,
          stations: updateStation(nextState.stations, "bank", "active", "attempted")
        };
        return nextState;
      }

      nextState = {
        ...nextState,
        bank: {
          executed,
          reason
        },
        stations: updateStation(
          nextState.stations,
          "bank",
          executed ? "pass" : "fail",
          reason
        ),
        pending: false
      };
      return nextState;
    }
    default:
      return nextState;
  }
}

export function runStoreReducer(state: RunStoreState, action: RunStoreAction): RunStoreState {
  switch (action.type) {
    case "reset":
      return createInitialRunState();
    case "prime":
      return {
        ...createInitialRunState(),
        scenario: action.scenario,
        fallbackMode: action.fallbackMode,
        proposal: {
          request: action.proposal,
          intentId: null,
          accepted: false
        },
        counterfactual: null
      };
    case "proposalAccepted":
      return state.proposal
        ? {
            ...state,
            proposal: {
              ...state.proposal,
              intentId: action.intentId,
              accepted: true
            }
          }
        : state;
    case "runStarted":
      return {
        ...state,
        runId: action.runId,
        pending: true
      };
    case "streamMode":
      return {
        ...state,
        streamMode: action.mode
      };
    case "applyEvent":
      return reduceContractEvent(state, action.event);
    case "verificationUpdated":
      return {
        ...state,
        verification: {
          verified: action.verification.verified,
          chainHead:
            action.verification.chain_head ??
            action.verification.ledger_entry_hash,
          proofHash: action.verification.proof_hash,
          ledgerEntryHash: action.verification.ledger_entry_hash,
          ledgerChainValid: action.verification.ledger_chain_valid,
          packetEntryValid: action.verification.packet_entry_valid,
          tamperedField: action.tamperedField ?? state.verification?.tamperedField ?? null,
          brokenRecordIndex: action.verification.broken_record_index ?? null
        }
      };
    case "setReviewReviewerId":
      return state.review
        ? {
            ...state,
            review: {
              ...state.review,
              reviewerId: action.reviewerId
            }
          }
        : state;
    case "setError":
      return {
        ...state,
        error: action.message
      };
    case "markComplete":
      return {
        ...state,
        pending: false
      };
    default:
      return state;
  }
}

function titleForEvent(eventType: string): string {
  return eventType
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function detailForEvent(event: ContractRunEvent): string {
  switch (event.event) {
    case "PLAN_STARTED":
      return "The workflow definition was loaded and the deterministic path was planned.";
    case "EVIDENCE_RETRIEVED":
      return "Evidence loaded (seeded) for this run.";
    case "EXTRACTION_STARTED":
      return "Extraction processing started.";
    case "EXTRACTION_SEALED":
      return "The typed extraction was sealed before the gates ran.";
    case "TOOL_CALLED":
      return "A simulated tool call was logged.";
    case "GATE_STARTED":
      return "A gate moved into active evaluation.";
    case "GATE_COMPLETED":
      return "A gate finished with backend-supplied status and reasons.";
    case "DECISION_MADE":
      return "The backend emitted the final decision.";
    case "REVIEW_REQUIRED":
      return "The run paused for human review before token issuance.";
    case "REVIEW_COMPLETED":
      return "A reviewer recorded an approve or reject action in the proof chain.";
    case "TOKEN_ISSUED":
      return "The backend issued an ALLOW token.";
    case "PROOF_SEALED":
      return "The proof packet was sealed.";
    case "EXECUTION_ATTEMPTED":
      return "The execution boundary responded to the run outcome.";
    default:
      return "Backend event received.";
  }
}

export function buildTimelineFromRunState(state: RunStoreState): EventTimelineResponse | null {
  if (state.runId === null || state.events.length === 0) {
    return null;
  }

  const events: OrchestratorEvent[] = state.events.map((event, index) => ({
    index,
    event_type: event.event,
    run_id: event.run_id,
    title: titleForEvent(event.event),
    detail: detailForEvent(event),
    payload: event.data
  }));

  return {
    run_id: state.runId,
    events
  };
}

export function buildRunSummaryFromRunState(state: RunStoreState): RunSummaryResponse | null {
  if (state.runId === null || state.decision === null || state.proposal === null) {
    return null;
  }

  return {
    scenario: state.scenario ?? "unknown",
    run_id: state.runId,
    final_decision: state.decision.value,
    allow_execution: state.decision.value === "ALLOW",
    token_issued: state.token?.issued ?? false,
    mock_bank_status: state.bank ? (state.bank.executed ? "ACCEPTED" : "REJECTED") : "PENDING",
    mock_bank_reason_code: state.bank?.reason ?? "PENDING",
    proof_hash: state.proof?.chainHash ?? "",
    ledger_entry_hash: state.proof?.chainHash ?? "",
    timeline_events_count: state.events.length
  };
}

interface RunStoreValue {
  state: RunStoreState;
  dispatch: Dispatch<RunStoreAction>;
}

const RunStoreContext = createContext<RunStoreValue | null>(null);

export function RunStoreProvider({ children }: PropsWithChildren): JSX.Element {
  const [state, dispatch] = useReducer(runStoreReducer, undefined, createInitialRunState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <RunStoreContext.Provider value={value}>{children}</RunStoreContext.Provider>;
}

export function useRunStore(): RunStoreValue {
  const value = useContext(RunStoreContext);
  if (value === null) {
    throw new Error("useRunStore must be used within RunStoreProvider.");
  }
  return value;
}
