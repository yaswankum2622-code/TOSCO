import type { PropsWithChildren } from "react";

function RightStack({ children }: PropsWithChildren) {
  return (
    <section className="console-column console-column--right" data-testid="right-stack" aria-label="Right stack">
      <div className="slot-body">{children ?? <div className="slot-placeholder">Mount slot</div>}</div>
    </section>
  );
}

export default RightStack;
