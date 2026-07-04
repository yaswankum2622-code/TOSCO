import type { EventTimelineResponse } from "../api/types";

interface EventTimelineProps {
  timeline: EventTimelineResponse | null;
}

const HIGHLIGHT_EVENT_TYPES = new Set([
  "DECISION_MADE",
  "PROOF_SEALED",
  "CLEARANCE_TOKEN_ISSUED",
  "CLEARANCE_TOKEN_SKIPPED",
  "EXECUTION_ACCEPTED",
  "EXECUTION_REJECTED"
]);

function EventTimeline({ timeline }: EventTimelineProps) {
  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-heading">
      <div className="panel__header">
        <h2 id="timeline-heading">Event Timeline</h2>
        <span className="mono-label">{timeline ? `${timeline.events.length} events` : "No run loaded"}</span>
      </div>
      {!timeline ? (
        <p className="empty-state">Timeline events will appear here after a scenario run starts.</p>
      ) : (
        <ol className="timeline-list">
          {timeline.events.map((event) => {
            const highlighted = HIGHLIGHT_EVENT_TYPES.has(event.event_type);
            return (
              <li
                key={`${event.run_id}-${event.index}-${event.event_type}`}
                className={`timeline-item ${highlighted ? "timeline-item--highlight" : ""}`}
              >
                <div className="timeline-item__header">
                  <span className="timeline-item__index">{String(event.index).padStart(2, "0")}</span>
                  <span className="timeline-item__type">{event.event_type}</span>
                </div>
                <div className="timeline-item__body">
                  <h3>{event.title}</h3>
                  <p>{event.detail}</p>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

export default EventTimeline;
