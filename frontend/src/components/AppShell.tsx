import type { ReactNode } from "react";

import CenterConsole from "./CenterConsole";
import LeftColumn from "./LeftColumn";
import RightStack from "./RightStack";
import ScreenVignetteFlash from "./ScreenVignetteFlash";
import SettlementHero from "./SettlementHero";

interface AppShellProps {
  workflowId: string | null;
  runId: string | null;
  fallbackMode: boolean;
  decision: string | null;
  onReset?: () => void;
  resetting?: boolean;
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

function AppShell({
  workflowId,
  runId,
  fallbackMode,
  decision,
  onReset,
  resetting = false,
  left,
  center,
  right
}: AppShellProps) {
  const shellClassName = [
    "console-shell",
    runId !== null ? "console-shell--armed" : "",
    decision !== null ? "console-shell--decided" : "",
    decision !== null ? `console-shell--verdict-${decision.toLowerCase()}` : ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClassName}>
      <ScreenVignetteFlash decision={decision} />
      <header className="console-topbar" data-testid="console-topbar">
        <div className="console-topbar__brand">
          <span className="console-mark">TOSCO</span>
        </div>
        <span className="console-topbar__separator" aria-hidden="true">
          |
        </span>
        <div className="console-topbar__meta">
          <span className="topbar-label">workflow</span>
          <code className="topbar-mono">{workflowId ?? "pending"}</code>
        </div>
        <span className="console-topbar__separator" aria-hidden="true">
          |
        </span>
        <div className="console-topbar__meta">
          <span className="topbar-label">run</span>
          <code className="topbar-mono">{runId ?? "pending"}</code>
        </div>
        <span className="console-topbar__separator" aria-hidden="true">
          |
        </span>
        <div className="console-topbar__status-wrap">
          {onReset ? (
            <button
              className="ghost-button console-topbar__reset"
              type="button"
              onClick={onReset}
              disabled={resetting}
              data-testid="reset-demo-button"
            >
              {resetting ? "Resetting…" : "Reset Demo"}
            </button>
          ) : null}
          <span
            className={`live-pill ${fallbackMode ? "live-pill--fallback" : "live-pill--sandbox"}`}
            data-testid="fallback-pill"
          >
            <span className="live-pill__dot" aria-hidden="true" />
            <span className="live-pill__label">LIVE {fallbackMode ? "FALLBACK" : "SANDBOX"}</span>
          </span>
        </div>
      </header>

      <div className="console-main">
        <SettlementHero collapsed={runId !== null} />
        <main className="console-grid" data-testid="console-grid">
          <LeftColumn railLabel="Intake">{left}</LeftColumn>
          <CenterConsole railLabel="Clearance bus">{center}</CenterConsole>
          <RightStack railLabel="Outcome">{right}</RightStack>
        </main>
      </div>
    </div>
  );
}

export default AppShell;
