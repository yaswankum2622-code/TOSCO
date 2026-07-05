import type { OrchestratorEvent } from "../api/types";

interface TimelineEventCardProps {
  event: OrchestratorEvent;
}

const HIGHLIGHT_EVENT_TYPES = new Set([
  "DECISION_MADE",
  "PROOF_SEALED",
  "TOKEN_ISSUED",
  "CLEARANCE_TOKEN_ISSUED",
  "CLEARANCE_TOKEN_SKIPPED",
  "VULTR_EXTRACTION_STARTED",
  "VULTR_EXTRACTION_SUCCEEDED",
  "VULTR_EXTRACTION_FALLBACK",
  "EXECUTION_ACCEPTED",
  "EXECUTION_REJECTED",
  "EXECUTION_ATTEMPTED"
]);

const EVENT_LABELS: Record<string, string> = {
  VULTR_EXTRACTION_STARTED: "Vultr extraction started",
  VULTR_EXTRACTION_SUCCEEDED: "Vultr extraction succeeded",
  VULTR_EXTRACTION_FALLBACK: "Fallback extraction used",
  TOKEN_ISSUED: "Token issued"
};

function stringPayload(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function numberPayload(payload: Record<string, unknown>, key: string): number | null {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function booleanPayload(payload: Record<string, unknown>, key: string): boolean | null {
  const value = payload[key];
  return typeof value === "boolean" ? value : null;
}

function payloadHighlights(eventType: string, payload: Record<string, unknown>): string[] {
  const highlights: string[] = [];
  const gateId = stringPayload(payload, "gate_id");
  const toolId = stringPayload(payload, "tool_id");
  const reasonCode = stringPayload(payload, "reason_code");
  const source = stringPayload(payload, "source");
  const latency = numberPayload(payload, "latency_ms");
  const tokenId = stringPayload(payload, "token_id");
  const reason = stringPayload(payload, "reason");
  const fallbackMode = booleanPayload(payload, "fallback_mode");
  const simulated = booleanPayload(payload, "simulated");

  if (gateId) {
    highlights.push(gateId);
  }
  if (toolId) {
    highlights.push(toolId);
  }
  if (simulated === true) {
    highlights.push("simulated");
  }
  if (reasonCode) {
    highlights.push(reasonCode);
  }
  if (source) {
    highlights.push(source.toUpperCase());
  }
  if (latency !== null) {
    highlights.push(`${latency}ms`);
  }
  if (tokenId) {
    highlights.push(tokenId);
  }
  if (reason) {
    highlights.push(reason);
  }
  if (fallbackMode === true) {
    highlights.push("FALLBACK");
  }

  return highlights.slice(0, 4);
}

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
  const displayType =
    event.event_type === "EXTRACTION_STARTED" && event.payload["fallback_mode"] === true
      ? "Fallback extraction used"
      : EVENT_LABELS[event.event_type] ?? event.event_type;
  const toneClass = eventToneClass(event.event_type);
  const highlights = payloadHighlights(event.event_type, event.payload);

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
        {highlights.length > 0 ? (
          <div className="timeline-event-card__chips">
            {highlights.map((highlight, index) => (
              <span key={`${event.index}-${highlight}-${index}`} className="chip timeline-event-card__chip">
                {highlight}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </article>
  );
}

export default TimelineEventCard;
