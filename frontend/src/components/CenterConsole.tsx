import type { PropsWithChildren } from "react";

function CenterConsole({ children }: PropsWithChildren) {
  return (
    <section className="console-column console-column--center" data-testid="center-console" aria-label="Center console">
      <div className="slot-body">{children ?? <div className="slot-placeholder">Mount slot</div>}</div>
    </section>
  );
}

export default CenterConsole;
