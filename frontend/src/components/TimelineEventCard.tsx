import type { OrchestratorEvent } from "../api/types";

interface TimelineEventCardProps {
  event: OrchestratorEvent;
}

const HIGHLIGHT_EVENT_TYPES = new Set([
  "DECISION_MADE",
  "PROOF_SEALED",
  "CLEARANCE_TOKEN_ISSUED",
  "CLEARANCE_TOKEN_SKIPPED",
  "VULTR_EXTRACTION_STARTED",
  "VULTR_EXTRACTION_SUCCEEDED",
  "VULTR_EXTRACTION_FALLBACK",
  "EXECUTION_ACCEPTED",
  "EXECUTION_REJECTED"
]);

const EVENT_LABELS: Record<string, string> = {
  VULTR_EXTRACTION_STARTED: "Vultr extraction started",
  VULTR_EXTRACTION_SUCCEEDED: "Vultr extraction succeeded",
  VULTR_EXTRACTION_FALLBACK: "Fallback extraction used"
};

function eventToneClass(eventType: string): string {
  if (eventType === "VULTR_EXTRACTION_SUCCEEDED") {
    return "timeline-event-card--success";
  }
  if (eventType === "VULTR_EXTRACTION_FALLBACK") {
    return "timeline-event-card--fallback";
  }
  if (eventType === "VULTR_EXTRACTION_STARTED") {
    return "timeline-event-card--integration";
  }
  return "";
}

function TimelineEventCard({ event }: TimelineEventCardProps) {
  const highlighted = HIGHLIGHT_EVENT_TYPES.has(event.event_type);
  const displayType = EVENT_LABELS[event.event_type] ?? event.event_type;
  const toneClass = eventToneClass(event.event_type);

  return (
    <article
      className={`timeline-event-card ${highlighted ? "timeline-event-card--highlight" : ""} ${toneClass}`.trim()}
    >
      <div className="timeline-event-card__meta">
        <span className="timeline-event-card__index">{String(event.index).padStart(2, "0")}</span>
        <span className="timeline-event-card__type">{displayType}</span>
      </div>
      <div className="timeline-event-card__body">
        <h3>{event.title}</h3>
        <p>{event.detail}</p>
        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
      </div>
    </article>
  );
}

export default TimelineEventCard;
