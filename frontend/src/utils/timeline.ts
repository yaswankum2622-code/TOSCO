import type { OrchestratorEvent } from "../api/types";

export function findEvent(
  events: OrchestratorEvent[] | null | undefined,
  eventType: string
): OrchestratorEvent | undefined {
  return events?.find((event) => event.event_type === eventType);
}

export function findEvents(
  events: OrchestratorEvent[] | null | undefined,
  eventType: string
): OrchestratorEvent[] {
  return events?.filter((event) => event.event_type === eventType) ?? [];
}

export function payloadString(
  payload: Record<string, unknown> | undefined,
  key: string
): string | undefined {
  const value = payload?.[key];
  return typeof value === "string" ? value : undefined;
}

export function payloadNumber(
  payload: Record<string, unknown> | undefined,
  key: string
): number | undefined {
  const value = payload?.[key];
  return typeof value === "number" ? value : undefined;
}

export function payloadBoolean(
  payload: Record<string, unknown> | undefined,
  key: string
): boolean | undefined {
  const value = payload?.[key];
  return typeof value === "boolean" ? value : undefined;
}

export function payloadStringArray(
  payload: Record<string, unknown> | undefined,
  key: string
): string[] {
  const value = payload?.[key];
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string");
}

export function findGateCompleted(
  events: OrchestratorEvent[] | null | undefined,
  gateId: string
): OrchestratorEvent | undefined {
  return findEvents(events, "GATE_COMPLETED").find(
    (event) => payloadString(event.payload, "gate_id") === gateId
  );
}

export function extractDecisionEvent(
  events: OrchestratorEvent[] | null | undefined
): OrchestratorEvent | undefined {
  return findEvent(events, "DECISION_MADE");
}

export function extractProofEvent(
  events: OrchestratorEvent[] | null | undefined
): OrchestratorEvent | undefined {
  return findEvent(events, "PROOF_SEALED");
}

export function extractLedgerEvent(
  events: OrchestratorEvent[] | null | undefined
): OrchestratorEvent | undefined {
  return findEvent(events, "LEDGER_APPENDED");
}

export function extractTokenEvent(
  events: OrchestratorEvent[] | null | undefined
): OrchestratorEvent | undefined {
  return (
    findEvent(events, "CLEARANCE_TOKEN_ISSUED") ?? findEvent(events, "CLEARANCE_TOKEN_SKIPPED")
  );
}

export function extractExecutionFinalEvent(
  events: OrchestratorEvent[] | null | undefined
): OrchestratorEvent | undefined {
  return findEvent(events, "EXECUTION_ACCEPTED") ?? findEvent(events, "EXECUTION_REJECTED");
}
