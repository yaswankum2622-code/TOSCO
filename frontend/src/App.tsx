import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { ApiError, apiClient } from "./api/client";
import type {
  EventTimelineResponse,
  HealthResponse,
  ProofPacketResponse,
  RunSummaryResponse,
  ScenarioMetadata,
  VerifyRunResponse,
  WorkflowMetadata
} from "./api/types";
import AgentProposalPanel from "./components/AgentProposalPanel";
import BackendStatus from "./components/BackendStatus";
import CounterfactualStrip from "./components/CounterfactualStrip";
import DecisionHero from "./components/DecisionHero";
import EvidenceRail from "./components/EvidenceRail";
import EventTimeline from "./components/EventTimeline";
import GateChain from "./components/GateChain";
import Header from "./components/Header";
import MockBankCard from "./components/MockBankCard";
import ProofSeal from "./components/ProofSeal";
import ProofVerifier from "./components/ProofVerifier";
import ScenarioSwitcher from "./components/ScenarioSwitcher";
import ToolCallRail from "./components/ToolCallRail";
import WorkflowStrip from "./components/WorkflowStrip";

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
  const [proof, setProof] = useState<ProofPacketResponse | null>(null);
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

  const displayRun =
    activeRun && proof
      ? {
          ...activeRun,
          proof_hash: proof.proof_hash,
          ledger_entry_hash: proof.ledger_entry_hash
        }
      : activeRun;

  async function handleRunScenario(scenario: string) {
    setRunning(true);
    setError(null);

    try {
      const run = await apiClient.startRun(scenario);

      setActiveRun(run);
      setTimeline(null);
      setProof(null);
      setVerification(null);

      const [eventsResult, verificationResult, proofResult] = await Promise.allSettled([
        apiClient.getEvents(run.run_id),
        apiClient.verifyRun(run.run_id),
        apiClient.getProof(run.run_id)
      ]);

      const followUpErrors: string[] = [];

      if (eventsResult.status === "fulfilled") {
        setTimeline(eventsResult.value);
      } else {
        followUpErrors.push(formatError(eventsResult.reason));
      }

      if (verificationResult.status === "fulfilled") {
        setVerification(verificationResult.value);
      } else {
        followUpErrors.push(formatError(verificationResult.reason));
      }

      if (proofResult.status === "fulfilled") {
        setProof(proofResult.value);
      } else {
        followUpErrors.push(formatError(proofResult.reason));
      }

      if (followUpErrors.length > 0) {
        setError(followUpErrors.join(" "));
      }
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
      setProof(null);
      setVerification(null);
    } catch (resetError) {
      setError(formatError(resetError));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="floating-badge">Sandbox Rail</div>
      <Header />

      <div className="top-row">
        <BackendStatus health={health} loading={loading} error={backendError} />
        <WorkflowStrip workflows={workflows} activeRun={displayRun} />
      </div>

      <AnimatePresence>
        {error ? (
          <motion.section
            key={error}
            className="panel alert-panel"
            aria-live="polite"
            initial={{ opacity: 0, y: -14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <div className="panel__header">
              <h2>Backend Message</h2>
            </div>
            <p className="status-error">{error}</p>
          </motion.section>
        ) : null}
      </AnimatePresence>

      <main className="command-grid">
        <section className="command-column">
          <ScenarioSwitcher
            scenarios={scenarios}
            activeScenario={displayRun?.scenario ?? null}
            running={running}
            onRunScenario={handleRunScenario}
            onReset={handleReset}
          />
          <AgentProposalPanel run={displayRun} timeline={timeline} />
          <CounterfactualStrip run={displayRun} />
        </section>

        <section className="command-column command-column--center">
          <DecisionHero run={displayRun} timeline={timeline} />
          <GateChain timeline={timeline} />
          <ToolCallRail timeline={timeline} />
        </section>

        <section className="command-column">
          <EvidenceRail timeline={timeline} />
          <ProofSeal run={displayRun} verification={verification} />
          <ProofVerifier
            run={displayRun}
            verification={verification}
            onVerify={handleVerify}
            onTamper={handleTamper}
          />
          <MockBankCard run={displayRun} timeline={timeline} />
        </section>
      </main>

      <EventTimeline timeline={timeline} />
    </div>
  );
}

export default App;
