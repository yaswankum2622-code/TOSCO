import type { OrchestratorEvent } from "../api/types";

interface TimelineEventCardProps {
  event: OrchestratorEvent;
}

const HIGHLIGHT_EVENT_TYPES = new Set([
  "DECISION_MADE",
  "PROOF_SEALED",
  "CLEARANCE_TOKEN_ISSUED",
  "CLEARANCE_TOKEN_SKIPPED",
  "EXECUTION_ACCEPTED",
  "EXECUTION_REJECTED"
]);

function TimelineEventCard({ event }: TimelineEventCardProps) {
  const highlighted = HIGHLIGHT_EVENT_TYPES.has(event.event_type);

  return (
    <article className={`timeline-event-card ${highlighted ? "timeline-event-card--highlight" : ""}`}>
      <div className="timeline-event-card__meta">
        <span className="timeline-event-card__index">{String(event.index).padStart(2, "0")}</span>
        <span className="timeline-event-card__type">{event.event_type}</span>
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
