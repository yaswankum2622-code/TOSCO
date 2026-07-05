import type { PropsWithChildren } from "react";

function LeftColumn({ children }: PropsWithChildren) {
  return (
    <section className="console-column console-column--left" data-testid="left-column" aria-label="Left column">
      <div className="slot-body">{children ?? <div className="slot-placeholder">Mount slot</div>}</div>
    </section>
  );
}

export default LeftColumn;
