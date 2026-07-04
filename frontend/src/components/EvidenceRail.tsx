import type { EventTimelineResponse } from "../api/types";
import HashDisplay from "./HashDisplay";
import { findEvent, payloadNumber, payloadString, payloadStringArray } from "../utils/timeline";

interface EvidenceRailProps {
  timeline: EventTimelineResponse | null;
}

function EvidenceRail({ timeline }: EvidenceRailProps) {
  const evidenceEvent = findEvent(timeline?.events, "EVIDENCE_RETRIEVED");
  const extractionEvent = findEvent(timeline?.events, "EXTRACTION_SEALED");
  const evidenceTypes = payloadStringArray(evidenceEvent?.payload, "evidence_types");
  const requiredFields = payloadStringArray(extractionEvent?.payload, "required_fields");
  const extractionHash = payloadString(extractionEvent?.payload, "extraction_hash");
  const evidenceCount = payloadNumber(evidenceEvent?.payload, "evidence_count");

  return (
    <section className="panel" aria-labelledby="evidence-rail-heading">
      <div className="panel__header">
        <h2 id="evidence-rail-heading">Evidence Rail</h2>
        <span className="badge">Evidence hashed, not stored raw</span>
      </div>
      {!timeline ? (
        <p className="empty-state">Evidence retrieval and extraction events appear after a run starts.</p>
      ) : (
        <div className="rail-stack">
          <div className="rail-card">
            <span className="kv-label">Evidence count</span>
            <strong className="rail-card__value">{evidenceCount ?? "—"}</strong>
            <div className="chip-row">
              {evidenceTypes.length > 0 ? (
                evidenceTypes.map((type) => <span key={type} className="chip">{type}</span>)
              ) : (
                <span className="empty-state">No evidence types recorded.</span>
              )}
            </div>
          </div>
          <div className="rail-card">
            <HashDisplay label="Extraction hash" value={extractionHash} />
            <div className="chip-row">
              {requiredFields.length > 0 ? (
                requiredFields.map((field) => (
                  <span key={field} className="chip chip--paper">
                    {field}
                  </span>
                ))
              ) : (
                <span className="empty-state">Required fields will appear after sealing.</span>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default EvidenceRail;
