import type { EventTimelineResponse } from "../api/types";
import TimelineEventCard from "./TimelineEventCard";

interface EventTimelineProps {
  timeline: EventTimelineResponse | null;
}

function EventTimeline({ timeline }: EventTimelineProps) {
  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-heading">
      <div className="panel__header">
        <h2 id="timeline-heading">Run Pulse</h2>
        <span className="mono-label">{timeline ? `${timeline.events.length} steps` : "Standby"}</span>
      </div>
      {!timeline ? (
        <div className="timeline-empty-state">
          <span className="timeline-empty-state__orb" aria-hidden="true" />
          <p className="empty-state">A live pulse appears here once a scenario starts.</p>
        </div>
      ) : (
        <div className="timeline-list">
          {timeline.events.map((event) => (
            <TimelineEventCard
              key={`${event.run_id}-${event.index}-${event.event_type}`}
              event={event}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export default EventTimeline;
