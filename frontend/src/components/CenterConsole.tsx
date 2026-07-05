import type { PropsWithChildren } from "react";

interface CenterConsoleProps extends PropsWithChildren {
  railLabel?: string;
}

function CenterConsole({ children, railLabel = "Clearance bus" }: CenterConsoleProps) {
  return (
    <section className="console-column console-column--center" data-testid="center-console" aria-label="Clearance bus">
      <p className="console-rail-label">{railLabel}</p>
      <div className="slot-body">{children ?? <div className="slot-placeholder">Mount slot</div>}</div>
    </section>
  );
}

export default CenterConsole;
