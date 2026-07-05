import type { EventTimelineResponse } from "../api/types";
import TimelineEventCard from "./TimelineEventCard";

interface EventTimelineProps {
  timeline: EventTimelineResponse | null;
  collapsed?: boolean;
}

function EventTimeline({ timeline, collapsed = false }: EventTimelineProps) {
  const body = !timeline ? (
    <div className="timeline-empty-state">
      <span className="timeline-empty-state__orb" aria-hidden="true" />
      <p className="empty-state">Event stream opens once a clearance run starts.</p>
    </div>
  ) : (
    <div className="timeline-list">
      {timeline.events.map((event) => (
        <TimelineEventCard key={`${event.run_id}-${event.index}-${event.event_type}`} event={event} />
      ))}
    </div>
  );

  return (
    <details
      className={`system-lane timeline-panel ${collapsed ? "timeline-panel--folded" : ""}`}
      open={!collapsed}
      data-testid="event-log"
    >
      <summary className="system-lane__header timeline-panel__summary">
        <h2 id="timeline-heading">Event log</h2>
        <span className="mono-label">{timeline ? `${timeline.events.length} steps` : "Standby"}</span>
      </summary>
      <div className="system-lane__body">{body}</div>
    </details>
  );
}

export default EventTimeline;
