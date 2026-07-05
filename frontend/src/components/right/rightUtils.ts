import type { RunGateState, RunStoreState } from "../../run/store";

export function normalizeReasonCode(reasonCode: string | null): string {
  if (reasonCode === "REALITY_OWNER_MISMATCH_FREEZE") {
    return "REALITY_OWNER_MISMATCH";
  }
  return reasonCode ?? "-";
}

function gateSeverity(gate: RunGateState): number {
  if (gate.status === "FAIL") {
    return 2;
  }
  if (gate.status === "WARN") {
    return 1;
  }
  return 0;
}

export function failedOrWarnedGates(state: RunStoreState): RunGateState[] {
  return state.gates.filter((gate) => gate.status === "FAIL" || gate.status === "WARN");
}

export function deriveDecisionReasonCodes(state: RunStoreState): string[] {
  const highlighted = failedOrWarnedGates(state);
  const source =
    highlighted.length > 0
      ? highlighted
      : state.gates.filter((gate) => gate.status === "PASS").slice(-1);

  return source
    .map((gate) => normalizeReasonCode(gate.reasonCode))
    .filter((reasonCode, index, values) => reasonCode !== "-" && values.indexOf(reasonCode) === index);
}

export function deriveDecisionHumanReason(state: RunStoreState): string {
  const prioritized = [...state.gates]
    .filter((gate) => gate.status !== "idle" && gate.status !== "active")
    .sort((left, right) => gateSeverity(left) - gateSeverity(right));
  const selected = prioritized[prioritized.length - 1];

  if (selected?.humanReason) {
    return selected.humanReason;
  }

  return state.decision?.humanReason ?? "Awaiting backend decision.";
}

export function deriveFailedSignals(state: RunStoreState): string[] {
  return failedOrWarnedGates(state).map((gate) => gate.id);
}

export function decisionTone(decision: string | null): "allow" | "warn" | "deny" | "mute" {
  switch (decision) {
    case "ALLOW":
      return "allow";
    case "ESCALATE":
      return "warn";
    case "BLOCK":
    case "FREEZE":
      return "deny";
    default:
      return "mute";
  }
}
