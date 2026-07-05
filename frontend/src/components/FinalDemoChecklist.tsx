import type { VerifyRunResponse, VultrStatusResponse } from "../api/types";
import type {
  RunBankState,
  RunDecisionState,
  RunGateState,
  RunProofState,
  RunProposalState,
  RunStation,
  RunTokenState
} from "../run/store";

interface FinalDemoChecklistProps {
  proposal: RunProposalState | null;
  stations: RunStation[];
  gates: RunGateState[];
  decision: RunDecisionState | null;
  token: RunTokenState | null;
  bank: RunBankState | null;
  proof: RunProofState | null;
  fallbackMode: boolean;
  verification: VerifyRunResponse | null;
  vultrStatus: VultrStatusResponse | null;
}

interface ChecklistItem {
  label: string;
  complete: boolean;
  detail?: string;
}

function stationComplete(stations: RunStation[], id: string): boolean {
  const station = stations.find((item) => item.id === id);
  return station?.status === "pass" || station?.status === "fail";
}

function FinalDemoChecklist({
  proposal,
  stations,
  gates,
  decision,
  token,
  bank,
  proof,
  fallbackMode,
  verification,
  vultrStatus
}: FinalDemoChecklistProps) {
  const completedGates = gates.filter((gate) => gate.status === "PASS" || gate.status === "WARN" || gate.status === "FAIL").length;
  const tokenRuleSatisfied =
    decision === null
      ? false
      : decision.value === "ALLOW"
        ? token?.issued === true
        : token === null;

  const items: ChecklistItem[] = [
    {
      label: "Agent proposed payment",
      complete: proposal?.accepted === true
    },
    {
      label: "Evidence loaded (seeded)",
      complete: stationComplete(stations, "evidence")
    },
    {
      label: "Extraction sealed",
      complete: stationComplete(stations, "extraction")
    },
    {
      label: "Five deterministic gates executed",
      complete: completedGates === gates.length,
      detail: `${completedGates}/${gates.length} recorded`
    },
    {
      label: "Proof Packet sealed",
      complete: proof?.sealed === true
    },
    {
      label: "Clearance token issued only for ALLOW",
      complete: tokenRuleSatisfied
    },
    {
      label: "Mock Bank enforced token",
      complete: bank !== null
    },
    {
      label: "Sentinel recorded attack pattern",
      complete: decision !== null && decision.value !== "ALLOW"
    },
    {
      label: "Tamper demo breaks verification",
      complete: verification?.verified === false
    },
    {
      label: "Vultr extraction path available",
      complete: vultrStatus?.mode === "serverless-inference",
      detail: fallbackMode ? "Fallback extraction used" : "Live extraction used"
    }
  ];

  return (
    <section className="panel final-demo-checklist" aria-labelledby="final-demo-checklist-heading">
      <div className="panel__header">
        <h2 id="final-demo-checklist-heading">Final Demo Checklist</h2>
        <span className="mono-label">{items.filter((item) => item.complete).length}/{items.length} complete</span>
      </div>
      <ul className="checklist-list">
        {items.map((item) => (
          <li
            key={item.label}
            className={`checklist-item ${item.complete ? "checklist-item--complete" : ""}`}
            role="checkbox"
            aria-checked={item.complete}
          >
            <span className="checklist-item__marker" aria-hidden="true">
              {item.complete ? "OK" : "--"}
            </span>
            <span className="checklist-item__copy">
              <strong>{item.label}</strong>
              {item.detail ? <small>{item.detail}</small> : null}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default FinalDemoChecklist;
