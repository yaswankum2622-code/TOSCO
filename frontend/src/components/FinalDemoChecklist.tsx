import type {
  EventTimelineResponse,
  RunSummaryResponse,
  VerifyRunResponse,
  VultrStatusResponse
} from "../api/types";
import { findEvent, findEvents } from "../utils/timeline";

interface FinalDemoChecklistProps {
  activeRun: RunSummaryResponse | null;
  timeline: EventTimelineResponse | null;
  verification: VerifyRunResponse | null;
  vultrStatus: VultrStatusResponse | null;
}

interface ChecklistItem {
  label: string;
  complete: boolean;
  detail?: string;
}

function FinalDemoChecklist({
  activeRun,
  timeline,
  verification,
  vultrStatus
}: FinalDemoChecklistProps) {
  const events = timeline?.events;
  const gateCount = findEvents(events, "GATE_COMPLETED").length;
  const tokenRuleSatisfied = activeRun
    ? activeRun.allow_execution
      ? activeRun.token_issued && Boolean(findEvent(events, "CLEARANCE_TOKEN_ISSUED"))
      : !activeRun.token_issued && Boolean(findEvent(events, "CLEARANCE_TOKEN_SKIPPED"))
    : false;

  const vultrDetail = findEvent(events, "VULTR_EXTRACTION_SUCCEEDED")
    ? "Live extraction used"
    : findEvent(events, "VULTR_EXTRACTION_FALLBACK")
      ? "Fallback extraction used"
      : vultrStatus?.configured
        ? "Ready for live extraction"
        : vultrStatus
          ? "Fallback ready"
          : "Awaiting status";

  const items: ChecklistItem[] = [
    {
      label: "Agent proposed payment",
      complete: Boolean(findEvent(events, "AGENT_PROPOSED"))
    },
    {
      label: "Evidence retrieved",
      complete: Boolean(findEvent(events, "EVIDENCE_RETRIEVED"))
    },
    {
      label: "Extraction sealed",
      complete: Boolean(findEvent(events, "EXTRACTION_SEALED"))
    },
    {
      label: "Six deterministic gates executed",
      complete: gateCount >= 6,
      detail: gateCount > 0 ? `${gateCount}/6 recorded` : undefined
    },
    {
      label: "Proof Packet sealed",
      complete: Boolean(findEvent(events, "PROOF_SEALED"))
    },
    {
      label: "SHA-256 ledger appended",
      complete: Boolean(findEvent(events, "LEDGER_APPENDED"))
    },
    {
      label: "Clearance token issued only for ALLOW",
      complete: tokenRuleSatisfied
    },
    {
      label: "Mock Bank enforced token",
      complete:
        Boolean(findEvent(events, "EXECUTION_ATTEMPTED")) &&
        Boolean(findEvent(events, "EXECUTION_ACCEPTED") ?? findEvent(events, "EXECUTION_REJECTED"))
    },
    {
      label: "Tamper demo breaks verification",
      complete: verification?.verified === false
    },
    {
      label: "Vultr extraction path available",
      complete: vultrStatus?.mode === "serverless-inference",
      detail: vultrDetail
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
