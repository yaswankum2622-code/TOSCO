import { shortHash } from "../utils/format";

interface HashDisplayProps {
  label: string;
  value?: string;
  verified?: boolean;
}

function HashDisplay({ label, value, verified }: HashDisplayProps) {
  return (
    <div className="hash-display">
      <div className="hash-display__meta">
        <span className="kv-label">{label}</span>
        {verified !== undefined ? (
          <span className={`status-pill ${verified ? "status-pill--online" : "status-pill--offline"}`}>
            {verified ? "Verified" : "Broken"}
          </span>
        ) : null}
      </div>
      <code title={value}>{shortHash(value)}</code>
    </div>
  );
}

export default HashDisplay;
