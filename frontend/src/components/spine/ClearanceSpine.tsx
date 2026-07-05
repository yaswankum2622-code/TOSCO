import type { ReactNode } from "react";

import type { ContractRunEvent } from "../../api/types";
import type { RunGateState, RunStoreState, StationStatus } from "../../run/store";
import { shortHash } from "../../utils/format";
import SystemSealMark from "../SystemSealMark";
import DecisionStamp from "./DecisionStamp";
import SpineSegment from "./SpineSegment";
import StationRow from "./StationRow";

interface ClearanceSpineProps {
  state: RunStoreState;
}

interface DerivedSpineRow {
  id: string;
  label: string;
  status: StationStatus;
  detail: ReactNode;
  aux?: ReactNode;
  overlay?: ReactNode;
  detailTestId?: string;
}

const GATE_LABELS: Record<string, string> = {
  G1_EVIDENCE: "G1 EVIDENCE",
  G2_GROUNDEDNESS: "G2 GROUNDEDNESS",
  G3_POLICY: "G3 POLICY",
  G4_RISK: "G4 RISK",
  G5_REALITY: "G5 REALITY"
};

const RETRIEVE_PASSES = 5;

function findEvents(events: ContractRunEvent[], eventType: string): ContractRunEvent[] {
  return events.filter((event) => event.event === eventType);
}

function findLastEvent(events: ContractRunEvent[], eventType: string): ContractRunEvent | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].event === eventType) {
      return events[index];
    }
  }
  return null;
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

function hasResolved(status: StationStatus): boolean {
  return status === "pass" || status === "fail";
}

function statusFromGate(gate: RunGateState): StationStatus {
  switch (gate.status) {
    case "PASS":
      return "pass";
    case "WARN":
    case "FAIL":
      return "fail";
    case "active":
      return "active";
    default:
      return "idle";
  }
}

function sourceLabel(extractor: string | null, fallbackMode: boolean): string {
  if (fallbackMode) {
    return "Fallback";
  }
  if (extractor === null) {
    return "Vultr";
  }
  return extractor.toLowerCase().includes("fallback") ? "Fallback" : "Vultr";
}

function displaySource(source: string | null, extractor: string | null, fallbackMode: boolean): string {
  if (source === "vultr") {
    return "Vultr";
  }
  if (source === "fallback") {
    return "Fallback";
  }
  return sourceLabel(extractor, fallbackMode);
}

function buildRetrieveAux(retrievedPasses: Set<number>): ReactNode {
  return (
    <div className="retrieve-pass-dots" aria-label="Retrieval passes">
      {Array.from({ length: RETRIEVE_PASSES }, (_, index) => {
        const pass = index + 1;
        const filled = retrievedPasses.has(pass);
        return (
          <span
            key={pass}
            className={`retrieve-pass-dot ${filled ? "retrieve-pass-dot--filled" : ""}`}
            data-testid={`retrieve-pass-${pass}`}
            data-status={filled ? "pass" : "idle"}
            aria-hidden="true"
          />
        );
      })}
    </div>
  );
}

export function buildClearanceSpineRows(state: RunStoreState): DerivedSpineRow[] {
  const proposalIntentId = state.proposal?.intentId ?? "pending";
  const proposeStatus: StationStatus = state.runId ? "pass" : state.proposal ? "active" : "idle";

  const evidenceStation = state.stations.find((station) => station.id === "evidence");
  const retrievalEvents = findEvents(state.events, "EVIDENCE_RETRIEVED");
  const retrievedPasses = new Set<number>();
  const retrievedEvidenceTypes: string[] = [];
  for (const event of retrievalEvents) {
    const retrievalPass = numberValue(event.data, "retrieval_pass");
    const evidenceType = stringValue(event.data, "evidence_type");
    if (retrievalPass !== null) {
      retrievedPasses.add(retrievalPass);
    }
    if (evidenceType && !retrievedEvidenceTypes.includes(evidenceType)) {
      retrievedEvidenceTypes.push(evidenceType);
    }
  }
  const retrieveStatus = evidenceStation?.status ?? (state.workflow ? "active" : "idle");
  const retrieveDetail =
    retrievedEvidenceTypes.length > 0
      ? `${retrievedPasses.size}/${RETRIEVE_PASSES} ${retrievedEvidenceTypes.join(" | ")}`
      : `${retrievedPasses.size}/${RETRIEVE_PASSES} awaiting`;

  const extractionStation = state.stations.find((station) => station.id === "extraction");
  const extractionStarted = findLastEvent(state.events, "EXTRACTION_STARTED");
  const extractionSealed = findLastEvent(state.events, "EXTRACTION_SEALED");
  const fallbackMode =
    booleanValue(extractionSealed?.data ?? {}, "fallback_mode") ??
    booleanValue(extractionStarted?.data ?? {}, "fallback_mode") ??
    state.fallbackMode;
  const extractionLatency =
    numberValue(extractionSealed?.data ?? {}, "latency_ms") ??
    numberValue(extractionStarted?.data ?? {}, "latency_ms");
  const extractionSource =
    displaySource(
      stringValue(extractionSealed?.data ?? {}, "source") ??
        stringValue(extractionStarted?.data ?? {}, "source"),
      stringValue(extractionStarted?.data ?? {}, "extractor"),
      fallbackMode
    );
  const extractionStatus = extractionStation?.status ?? "idle";
  const extractionDetail =
    extractionStatus === "idle"
      ? "awaiting extraction"
      : `${extractionSource}${extractionLatency !== null ? ` | ${extractionLatency}ms` : ""}`;

  const toolsStation = state.stations.find((station) => station.id === "tools");
  const toolEvents = findEvents(state.events, "TOOL_CALLED");
  const toolIds = toolEvents
    .map((event) => stringValue(event.data, "tool_id"))
    .filter((toolId): toolId is string => toolId !== null);
  const toolLatencies = toolEvents
    .map((event) => numberValue(event.data, "latency_ms"))
    .filter((latency): latency is number => latency !== null);
  const toolsDetail =
    toolIds.length > 0
      ? `${toolIds
          .map((toolId, index) => `${toolId}${toolLatencies[index] !== undefined ? `(${toolLatencies[index]}ms)` : ""}`)
          .join(" | ")} | simulated`
      : toolsStation?.status === "active"
        ? "awaiting tool calls"
        : "no tool calls";

  const decisionStation = state.stations.find((station) => station.id === "decision");
  const decisionStatus =
    state.decision === null
      ? decisionStation?.status ?? "idle"
      : state.decision.value === "ALLOW"
        ? "pass"
        : "fail";
  const decisionDetail = state.decision?.value ?? "awaiting decision";

  const tokenStation = state.stations.find((station) => station.id === "token");
  const tokenStatus: StationStatus = state.token?.issued
    ? "pass"
    : state.decision && state.decision.value !== "ALLOW"
      ? "fail"
      : tokenStation?.status ?? "idle";
  const tokenDetail = state.token?.issued
    ? `ISSUED | ${state.token.tokenShort ?? shortHash(state.token.raw ?? "")}${state.token.exp ? ` | ${state.token.exp}` : ""}`
    : state.decision && state.decision.value !== "ALLOW"
      ? "SKIPPED"
      : tokenStation?.status === "active"
        ? "AWAITING TOKEN"
        : "awaiting token";

  const bankStation = state.stations.find((station) => station.id === "bank");
  const bankStatus: StationStatus = state.bank
    ? state.bank.executed
      ? "pass"
      : "fail"
    : bankStation?.status ?? "idle";
  const bankDetail = state.bank
    ? `${state.bank.executed ? "EXECUTED" : "REJECTED"} | ${state.bank.reason}`
    : bankStation?.status === "active"
      ? "AWAITING EXECUTION"
      : "awaiting execution";

  const proofStation = state.stations.find((station) => station.id === "proof");
  const proofStatus: StationStatus = state.proof?.sealed
    ? "pass"
    : proofStation?.status === "active"
      ? "active"
      : proofStation?.status ?? "idle";
  const proofDetail = state.proof?.chainHash
    ? shortHash(state.proof.chainHash, 12, 10)
    : proofStation?.status === "active"
      ? "sealing ledger"
      : "awaiting proof seal";

  const rows: DerivedSpineRow[] = [
    {
      id: "propose",
      label: "PROPOSE",
      status: proposeStatus,
      detail: state.proposal ? `INTENT ${proposalIntentId}` : "awaiting proposal"
    },
    {
      id: "retrieve",
      label: "Evidence loaded (seeded)",
      status: retrieveStatus,
      detail: retrieveDetail,
      aux: buildRetrieveAux(retrievedPasses)
    },
    {
      id: "extract",
      label: "EXTRACT",
      status: extractionStatus,
      detail: extractionDetail,
      aux: extractionSealed ? <SystemSealMark label="SEALED" testId="spine-extraction-seal" /> : undefined
    },
    {
      id: "tools",
      label: "TOOLS",
      status: toolsStation?.status ?? "idle",
      detail: toolsDetail
    }
  ];

  for (const gate of state.gates) {
    rows.push({
      id: gate.id,
      label: GATE_LABELS[gate.id] ?? gate.id,
      status: statusFromGate(gate),
      detail: gate.reasonCode ?? (gate.status === "active" ? "RUNNING" : gate.status.toUpperCase())
    });
  }

  rows.push(
    {
      id: "decision",
      label: "DECISION",
      status: decisionStatus,
      detail: decisionDetail,
      detailTestId: "final-decision",
      overlay: state.decision ? <DecisionStamp decision={state.decision.value} /> : undefined
    },
    {
      id: "review",
      label: "REVIEW",
      status:
        state.review?.required === true
          ? state.review.resolved
            ? state.review.action === "APPROVED"
              ? "pass"
              : "fail"
            : "active"
          : "idle",
      detail:
        state.review?.required === true
          ? state.review.resolved
            ? `${state.review.action ?? "DONE"} | ${state.review.reviewerId || "reviewer"}`
            : "awaiting reviewer"
          : "not required"
    },
    {
      id: "proof",
      label: "PROOF",
      status: proofStatus,
      detail: proofDetail,
      aux: state.proof?.sealed ? <SystemSealMark label="SEALED" testId="spine-proof-seal" /> : undefined
    },
    {
      id: "token",
      label: "TOKEN",
      status: tokenStatus,
      detail: tokenDetail
    },
    {
      id: "bank",
      label: "BANK",
      status: bankStatus,
      detail: bankDetail
    }
  );

  return rows;
}

function ClearanceSpine({ state }: ClearanceSpineProps) {
  const rows = buildClearanceSpineRows(state);
  const firstFailureIndex = rows.findIndex((row) => row.status === "fail");
  const floodActive = firstFailureIndex !== -1;

  return (
    <section
      className={`panel clearance-spine ${floodActive ? "clearance-spine--alert" : ""}`}
      aria-labelledby="clearance-spine-heading"
      data-alert={floodActive ? "true" : "false"}
    >
      <div className="panel__header">
        <h2 id="clearance-spine-heading">Clearance Spine</h2>
      </div>
      <div className="clearance-spine__list">
        {rows.map((row, index) => {
          const forceFail = firstFailureIndex !== -1 && index >= firstFailureIndex;
          const segmentStatus: StationStatus = forceFail ? "fail" : row.status;
          const shouldFill = hasResolved(row.status) || forceFail;
          const isLast = index === rows.length - 1;

          return (
            <div key={row.id} className="clearance-spine__step">
              <StationRow
                id={row.id}
                label={row.label}
                status={row.status}
                detail={row.detail}
                forceFail={forceFail}
                aux={row.aux}
                overlay={row.overlay}
                detailTestId={row.detailTestId}
              />
              {!isLast ? (
                <SpineSegment fromId={row.id} resolvedStatus={segmentStatus} shouldFill={shouldFill} />
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default ClearanceSpine;
