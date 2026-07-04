import type { EventTimelineResponse } from "../api/types";
import TimelineEventCard from "./TimelineEventCard";

interface EventTimelineProps {
  timeline: EventTimelineResponse | null;
}

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
