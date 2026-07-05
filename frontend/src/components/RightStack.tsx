import type { PropsWithChildren } from "react";

interface RightStackProps extends PropsWithChildren {
  railLabel?: string;
}

function RightStack({ children, railLabel = "Outcome" }: RightStackProps) {
  return (
    <section className="console-column console-column--right" data-testid="right-stack" aria-label="Outcome surface">
      <p className="console-rail-label">{railLabel}</p>
      <div className="slot-body">{children ?? <div className="slot-placeholder">Mount slot</div>}</div>
    </section>
  );
}

export default RightStack;
