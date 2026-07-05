import type { PropsWithChildren } from "react";

interface LeftColumnProps extends PropsWithChildren {
  railLabel?: string;
}

function LeftColumn({ children, railLabel = "Intake" }: LeftColumnProps) {
  return (
    <section className="console-column console-column--left" data-testid="left-column" aria-label="Intake channel">
      <p className="console-rail-label">{railLabel}</p>
      <div className="slot-body">{children ?? <div className="slot-placeholder">Mount slot</div>}</div>
    </section>
  );
}

export default LeftColumn;
