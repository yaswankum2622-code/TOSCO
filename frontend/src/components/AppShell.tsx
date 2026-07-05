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
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

function AppShell({
  workflowId,
  runId,
  fallbackMode,
  decision,
  left,
  center,
  right
}: AppShellProps) {
  return (
    <div className="console-shell">
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
          <LeftColumn>{left}</LeftColumn>
          <CenterConsole>{center}</CenterConsole>
          <RightStack>{right}</RightStack>
        </main>
      </div>
    </div>
  );
}

export default AppShell;
