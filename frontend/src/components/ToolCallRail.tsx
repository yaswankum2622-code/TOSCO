import type { EventTimelineResponse } from "../api/types";
import { findEvents, payloadBoolean, payloadString, payloadStringArray } from "../utils/timeline";

interface ToolCallRailProps {
  timeline: EventTimelineResponse | null;
}

function ToolCallRail({ timeline }: ToolCallRailProps) {
  const toolEvents = findEvents(timeline?.events, "TOOL_CALLED");

  return (
    <section className="panel" aria-labelledby="tool-call-rail-heading">
      <div className="panel__header">
        <h2 id="tool-call-rail-heading">Tool Call Rail</h2>
        <span className="mono-label">{toolEvents.length} tool calls</span>
      </div>
      {toolEvents.length === 0 ? (
        <p className="empty-state">Tool calls will populate from the backend timeline.</p>
      ) : (
        <div className="tool-rail">
          {toolEvents.map((event) => {
            const toolId = payloadString(event.payload, "tool_id") ?? "unknown_tool";
            const simulated = payloadBoolean(event.payload, "simulated");
            const signalKeys = payloadStringArray(event.payload, "signal_keys");

            return (
              <article key={`${event.run_id}-${event.index}`} className="tool-card">
                <div className="tool-card__header">
                  <strong>{toolId}</strong>
                  <span className={`status-pill ${simulated ? "status-pill--warning" : "status-pill--online"}`}>
                    {simulated ? "Simulated" : "Live"}
                  </span>
                </div>
                <div className="chip-row">
                  {signalKeys.map((signalKey) => (
                    <span key={signalKey} className="chip">
                      {signalKey}
                    </span>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default ToolCallRail;
