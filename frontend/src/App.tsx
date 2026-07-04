import { useEffect, useState } from "react";

import { ApiError, apiClient } from "./api/client";
import type {
  EventTimelineResponse,
  HealthResponse,
  RunSummaryResponse,
  ScenarioMetadata,
  VerifyRunResponse,
  WorkflowMetadata
} from "./api/types";
import BackendStatus from "./components/BackendStatus";
import EventTimeline from "./components/EventTimeline";
import Header from "./components/Header";
import ProofVerifier from "./components/ProofVerifier";
import RunSummaryCard from "./components/RunSummaryCard";
import ScenarioSwitcher from "./components/ScenarioSwitcher";

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The backend request failed.";
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowMetadata[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioMetadata[]>([]);
  const [activeRun, setActiveRun] = useState<RunSummaryResponse | null>(null);
  const [timeline, setTimeline] = useState<EventTimelineResponse | null>(null);
  const [verification, setVerification] = useState<VerifyRunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setBackendError(null);
      setError(null);

      try {
        const [healthResponse, workflowResponse, scenarioResponse] = await Promise.all([
          apiClient.getHealth(),
          apiClient.getWorkflows(),
          apiClient.getScenarios()
        ]);

        if (cancelled) {
          return;
        }

        setHealth(healthResponse);
        setWorkflows(workflowResponse);
        setScenarios(scenarioResponse);
      } catch (bootstrapError) {
        if (!cancelled) {
          const message = formatError(bootstrapError);
          setBackendError(message);
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRunScenario(scenario: string) {
    setRunning(true);
    setError(null);

    try {
      const run = await apiClient.startRun(scenario);
      const [eventsResponse, verificationResponse] = await Promise.all([
        apiClient.getEvents(run.run_id),
        apiClient.verifyRun(run.run_id)
      ]);

      setActiveRun(run);
      setTimeline(eventsResponse);
      setVerification(verificationResponse);
    } catch (runError) {
      setError(formatError(runError));
    } finally {
      setRunning(false);
    }
  }

  async function handleVerify() {
    if (!activeRun) {
      return;
    }

    setRunning(true);
    setError(null);

    try {
      const verificationResponse = await apiClient.verifyRun(activeRun.run_id);
      setVerification(verificationResponse);
    } catch (verificationError) {
      setError(formatError(verificationError));
    } finally {
      setRunning(false);
    }
  }

  async function handleTamper() {
    if (!activeRun) {
      return;
    }

    setRunning(true);
    setError(null);

    try {
      const tamperedVerification = await apiClient.tamperRun(activeRun.run_id);
      setVerification(tamperedVerification);
    } catch (tamperError) {
      setError(formatError(tamperError));
    } finally {
      setRunning(false);
    }
  }

  async function handleReset() {
    setRunning(true);
    setError(null);

    try {
      await apiClient.resetDemo();
      setActiveRun(null);
      setTimeline(null);
      setVerification(null);
    } catch (resetError) {
      setError(formatError(resetError));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app-shell">
      <Header />

      <main className="layout-grid">
        <section className="layout-column">
          <BackendStatus health={health} loading={loading} error={backendError} />

          {error ? (
            <section className="panel alert-panel" aria-live="polite">
              <div className="panel__header">
                <h2>Backend Message</h2>
              </div>
              <p className="status-error">{error}</p>
            </section>
          ) : null}

          <section className="panel workflow-panel" aria-labelledby="workflow-summary-heading">
            <div className="panel__header">
              <h2 id="workflow-summary-heading">Workflow Registry</h2>
              <span className="mono-label">{workflows.length} loaded</span>
            </div>
            {workflows.length === 0 ? (
              <p className="empty-state">Workflow metadata will appear after the backend responds.</p>
            ) : (
              <div className="workflow-strip">
                {workflows.map((workflow) => (
                  <article key={workflow.workflow_id} className="workflow-chip">
                    <h3>{workflow.workflow_name}</h3>
                    <dl>
                      <div>
                        <dt>Workflow ID</dt>
                        <dd>{workflow.workflow_id}</dd>
                      </div>
                      <div>
                        <dt>Evidence</dt>
                        <dd>{workflow.required_evidence_types.join(", ")}</dd>
                      </div>
                      <div>
                        <dt>Gates</dt>
                        <dd>{workflow.gates_to_run.join(", ")}</dd>
                      </div>
                      <div>
                        <dt>Tools</dt>
                        <dd>{workflow.tools_to_call.join(", ")}</dd>
                      </div>
                      <div>
                        <dt>Execution adapter</dt>
                        <dd>{workflow.execution_adapter}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>

          <ScenarioSwitcher
            scenarios={scenarios}
            activeScenario={activeRun?.scenario ?? null}
            running={running}
            onRunScenario={handleRunScenario}
            onReset={handleReset}
          />
        </section>

        <section className="layout-column layout-column--wide">
          <EventTimeline timeline={timeline} />
        </section>

        <section className="layout-column">
          <RunSummaryCard run={activeRun} />
          <ProofVerifier
            run={activeRun}
            verification={verification}
            onVerify={handleVerify}
            onTamper={handleTamper}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
