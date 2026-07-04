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
  VultrStatusResponse,
  WorkflowMetadata
} from "./api/types";
import AgentProposalPanel from "./components/AgentProposalPanel";
import BackendStatus from "./components/BackendStatus";
import CounterfactualStrip from "./components/CounterfactualStrip";
import DecisionHero from "./components/DecisionHero";
import DemoControlPanel from "./components/DemoControlPanel";
import EvidenceRail from "./components/EvidenceRail";
import EventTimeline from "./components/EventTimeline";
import FinalDemoChecklist from "./components/FinalDemoChecklist";
import GateChain from "./components/GateChain";
import Header from "./components/Header";
import MockBankCard from "./components/MockBankCard";
import ProofSeal from "./components/ProofSeal";
import ScenarioSwitcher from "./components/ScenarioSwitcher";
import ToolCallRail from "./components/ToolCallRail";
import VultrStatusCard from "./components/VultrStatusCard";
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
  const [vultrStatus, setVultrStatus] = useState<VultrStatusResponse | null>(null);
  const [activeRun, setActiveRun] = useState<RunSummaryResponse | null>(null);
  const [timeline, setTimeline] = useState<EventTimelineResponse | null>(null);
  const [proof, setProof] = useState<ProofPacketResponse | null>(null);
  const [verification, setVerification] = useState<VerifyRunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [vultrLoading, setVultrLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [vultrError, setVultrError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useVultr, setUseVultr] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setVultrLoading(true);
      setBackendError(null);
      setVultrError(null);
      setError(null);

      try {
        const [healthResponse, workflowResponse, scenarioResponse, vultrStatusResponse] =
          await Promise.allSettled([
          apiClient.getHealth(),
          apiClient.getWorkflows(),
          apiClient.getScenarios(),
          apiClient.getVultrStatus()
        ]);

        if (cancelled) {
          return;
        }

        const bootstrapErrors: string[] = [];

        if (healthResponse.status === "fulfilled") {
          setHealth(healthResponse.value);
        } else {
          bootstrapErrors.push(formatError(healthResponse.reason));
        }

        if (workflowResponse.status === "fulfilled") {
          setWorkflows(workflowResponse.value);
        } else {
          bootstrapErrors.push(formatError(workflowResponse.reason));
        }

        if (scenarioResponse.status === "fulfilled") {
          setScenarios(scenarioResponse.value);
        } else {
          bootstrapErrors.push(formatError(scenarioResponse.reason));
        }

        if (vultrStatusResponse.status === "fulfilled") {
          setVultrStatus(vultrStatusResponse.value);
        } else {
          setVultrStatus(null);
          setVultrError(formatError(vultrStatusResponse.reason));
        }

        if (bootstrapErrors.length > 0) {
          const message = bootstrapErrors.join(" ");
          setBackendError(message);
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setVultrLoading(false);
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
      const run = await apiClient.startRun(scenario, useVultr);

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
        <VultrStatusCard
          status={vultrStatus}
          loading={vultrLoading}
          error={vultrError}
          useVultr={useVultr}
          onToggleUseVultr={setUseVultr}
        />
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
          <DemoControlPanel
            activeRun={displayRun}
            verification={verification}
            onVerify={handleVerify}
            onTamper={handleTamper}
            onReset={handleReset}
            loading={running}
          />
          <MockBankCard run={displayRun} timeline={timeline} />
          <FinalDemoChecklist
            activeRun={displayRun}
            timeline={timeline}
            verification={verification}
            vultrStatus={vultrStatus}
          />
        </section>
      </main>

      <EventTimeline timeline={timeline} />
    </div>
  );
}

export default App;
