import type { ReactNode } from "react";

import type { StationStatus } from "../../run/store";

interface StationRowProps {
  id: string;
  label: string;
  status: StationStatus;
  detail: ReactNode;
  forceFail?: boolean;
  aux?: ReactNode;
  overlay?: ReactNode;
  detailTestId?: string;
}

function StationRow({ id, label, status, detail, forceFail = false, aux, overlay, detailTestId }: StationRowProps) {
  const displayStatus = forceFail ? "fail" : status;

  return (
    <article
      className={`station-row station-row--${status} ${forceFail ? "station-row--forced-fail" : ""} ${
        overlay ? "station-row--overlay" : ""
      }`}
      data-testid={`spine-row-${id}`}
      data-status={status}
      data-display-status={displayStatus}
    >
      <div className={`station-row__dot station-row__dot--${displayStatus}`} aria-hidden="true" />
      <div className="station-row__body">
        <span className="station-row__label">{label}</span>
        <div className="station-row__detail-wrap">
          <div className="station-row__detail mono-value" data-testid={detailTestId}>
            {detail}
          </div>
          {aux ? <div className="station-row__aux">{aux}</div> : null}
        </div>
      </div>
      {overlay ? <div className="station-row__overlay">{overlay}</div> : null}
    </article>
  );
}

export default StationRow;
