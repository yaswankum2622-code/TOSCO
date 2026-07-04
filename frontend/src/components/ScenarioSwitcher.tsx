import type { ScenarioMetadata } from "../api/types";

interface ScenarioSwitcherProps {
  scenarios: ScenarioMetadata[];
  activeScenario: string | null;
  running: boolean;
  onRunScenario: (scenario: string) => void;
  onReset: () => void;
}

const BUTTON_LABELS: Record<string, string> = {
  clean: "Run Clean Payment",
  injection: "Run Prompt Injection",
  forgery: "Run Forged Bank Change"
};

function ScenarioSwitcher({
  scenarios,
  activeScenario,
  running,
  onRunScenario,
  onReset
}: ScenarioSwitcherProps) {
  return (
    <section className="panel" aria-labelledby="scenario-switcher-heading">
      <div className="panel__header">
        <h2 id="scenario-switcher-heading">Scenario Control</h2>
        <button className="ghost-button" type="button" onClick={onReset} disabled={running}>
          Reset Demo State
        </button>
      </div>
      <div className="scenario-grid">
        {scenarios.map((scenario) => {
          const isActive = activeScenario === scenario.scenario;
          return (
            <article
              key={scenario.scenario}
              className={`scenario-card ${isActive ? "scenario-card--active" : ""}`}
            >
              <div className="scenario-card__meta">
                <span className="scenario-card__eyebrow">{scenario.scenario}</span>
                <span className="scenario-card__expectation">
                  Demo expectation: {scenario.expected_tosco_decision}
                </span>
              </div>
              <h3>{scenario.title}</h3>
              <p>{scenario.description}</p>
              <dl className="scenario-card__facts">
                <div>
                  <dt>Naive agent action</dt>
                  <dd>{scenario.expected_naive_agent_action}</dd>
                </div>
              </dl>
              <button
                className="primary-button"
                type="button"
                onClick={() => onRunScenario(scenario.scenario)}
                disabled={running}
              >
                {BUTTON_LABELS[scenario.scenario] ?? `Run ${scenario.title}`}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default ScenarioSwitcher;
