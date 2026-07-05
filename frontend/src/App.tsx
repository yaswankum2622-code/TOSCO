import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { ApiError, apiClient, formatCustomRunError } from "./api/client";
import { createRunEventsClient, type RunEventsClient } from "./api/events";
import { buildScenarioProposalRequest } from "./api/referenceProposals";
import CustomRunCard from "./components/CustomRunCard";
import type {
  AgentProposeRequest,
  ContractRunEvent,
  CustomRunRequest,
  ExecutionAttemptRequest,
  RunSnapshotResponse,
  ScenarioMetadata,
  VultrStatusResponse,
  WorkflowMetadata
} from "./api/types";
import AgentProposalPanel from "./components/AgentProposalPanel";
import AppShell from "./components/AppShell";
import CounterfactualStrip from "./components/CounterfactualStrip";
import EventTimeline from "./components/EventTimeline";
import NaiveAgentStrip from "./components/NaiveAgentStrip";
import ProofSeal from "./components/ProofSeal";
import ScenarioSwitcher from "./components/ScenarioSwitcher";
import VultrStatusCard from "./components/VultrStatusCard";
import ClearanceTokenCard from "./components/right/ClearanceTokenCard";
import DecisionCard from "./components/right/DecisionCard";
import HashVerifier from "./components/right/HashVerifier";
import ReviewerCard from "./components/right/ReviewerCard";
import MockBankExecutionCard from "./components/right/MockBankExecutionCard";
import ProofPacketViewer from "./components/right/ProofPacketViewer";
import SentinelMemoryCard from "./components/right/SentinelMemoryCard";
import ClearanceSpine from "./components/spine/ClearanceSpine";
import { buildTimelineFromRunState, RunStoreProvider, useRunStore } from "./run/store";

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The backend request failed.";
}

function parseTokenId(rawToken: string | null, tokenShort: string | null): string | null {
  if (rawToken) {
    try {
      const parsed = JSON.parse(rawToken) as { token_id?: unknown };
      return typeof parsed.token_id === "string" ? parsed.token_id : tokenShort;
    } catch {
      return tokenShort;
    }
  }

  return tokenShort;
}

function formatWorkflowLabel(workflowName: string | null, workflowId: string | null): string | null {
  if (workflowName) {
    return workflowName.replace(/^AI\s+/i, "").replace(/\s*&\s*Bank-Change\s+/i, " ");
  }

  if (workflowId) {
    return workflowId.replace(/_/g, " ");
  }

  return null;
}

function AppContent() {
  const { state: runState, dispatch } = useRunStore();
  const runStateRef = useRef(runState);
  const eventsClientRef = useRef<RunEventsClient | null>(null);

  const [workflows, setWorkflows] = useState<WorkflowMetadata[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioMetadata[]>([]);
  const [vultrStatus, setVultrStatus] = useState<VultrStatusResponse | null>(null);
  const [vultrLoading, setVultrLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [vultrError, setVultrError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useVultr, setUseVultr] = useState(false);

  useEffect(() => {
    runStateRef.current = runState;
  }, [runState]);

  if (eventsClientRef.current === null) {
    eventsClientRef.current = createRunEventsClient();
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setVultrLoading(true);
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

        if (healthResponse.status === "rejected") {
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
          setUseVultr(vultrStatusResponse.value.configured);
        } else {
          setVultrStatus(null);
          setVultrError(formatError(vultrStatusResponse.reason));
        }

        if (bootstrapErrors.length > 0) {
          const message = bootstrapErrors.join(" ");
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setVultrLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
      eventsClientRef.current?.stop();
    };
  }, []);

  const timeline = useMemo(() => buildTimelineFromRunState(runState), [runState]);
  const activeWorkflow =
    workflows.find((workflow) => workflow.workflow_id === (runState.workflow ?? workflows[0]?.workflow_id)) ?? workflows[0] ?? null;
  const workflowLabel = formatWorkflowLabel(activeWorkflow?.workflow_name ?? null, runState.workflow ?? activeWorkflow?.workflow_id ?? null);

  function buildExecutionRequest(snapshot: RunSnapshotResponse | null): ExecutionAttemptRequest | null {
    const currentState = runStateRef.current;
    const action = currentState.proposal?.request.action ?? snapshot?.intent?.action ?? null;
    if (currentState.runId === null || action === null) {
      return null;
    }

    return {
      run_id: currentState.runId,
      token: currentState.token?.raw ?? snapshot?.clearance_token ?? null,
      vendor_id: action.vendor_id,
      amount: action.amount
    };
  }

  async function handleAttemptExecution() {
    const currentState = runStateRef.current;
    const action = currentState.proposal?.request.action ?? null;

    if (currentState.runId === null || action === null) {
      return;
    }

    setRunning(true);
    setError(null);

    try {
      const payload: ExecutionAttemptRequest = {
        run_id: currentState.runId,
        token: currentState.token?.raw ?? null,
        vendor_id: action.vendor_id,
        amount: action.amount
      };
      const result = await apiClient.attemptExecution(payload);
      const event: ContractRunEvent = {
        event: "EXECUTION_ATTEMPTED",
        run_id: currentState.runId,
        ts: new Date().toISOString(),
        data: {
          token_id: parseTokenId(currentState.token?.raw ?? null, currentState.token?.tokenShort ?? null),
          amount: action.amount,
          bank_account_last4: action.bank_account_last4,
          executed: result.executed,
          reason: result.reason
        }
      };
      dispatch({ type: "applyEvent", event });
    } catch (attemptError) {
      setError(formatError(attemptError));
    } finally {
      setRunning(false);
    }
  }

  async function handleRunScenario(scenario: string) {
    eventsClientRef.current?.stop();
    setRunning(true);
    setError(null);

    try {
      const proposalRequest = buildScenarioProposalRequest(scenario);
      dispatch({
        type: "prime",
        scenario,
        proposal: proposalRequest,
        fallbackMode: false
      });

      const proposalResponse = await apiClient.proposeIntent(proposalRequest);
      dispatch({ type: "proposalAccepted", intentId: proposalResponse.intent_id });

      const runHandle = await apiClient.startRun(scenario, useVultr);
      dispatch({ type: "runStarted", runId: runHandle.run_id });

      eventsClientRef.current?.start(runHandle.run_id, {
        onEvent: async (event) => {
          dispatch({ type: "applyEvent", event });
        },
        onModeChange: (mode) => {
          dispatch({ type: "streamMode", mode });
        },
        onError: (streamError) => {
          const message = formatError(streamError);
          dispatch({ type: "setError", message });
          setError(message);
          setRunning(false);
        },
        onComplete: () => {
          dispatch({ type: "markComplete" });
          setRunning(false);
        },
        onReviewRequired: () => {
          setRunning(false);
        },
        buildExecutionRequest
      });
    } catch (runError) {
      const message = formatError(runError);
      dispatch({ type: "setError", message });
      setError(message);
      setRunning(false);
    }
  }

  async function handleRunCustom(payload: CustomRunRequest, proposal: AgentProposeRequest) {
    eventsClientRef.current?.stop();
    setRunning(true);
    setError(null);

    try {
      dispatch({
        type: "prime",
        scenario: "custom",
        proposal,
        fallbackMode: false
      });
      dispatch({ type: "proposalAccepted", intentId: "custom-intent" });

      const runHandle = await apiClient.startCustomRun(payload);
      dispatch({ type: "runStarted", runId: runHandle.run_id });

      eventsClientRef.current?.start(runHandle.run_id, {
        onEvent: async (event) => {
          dispatch({ type: "applyEvent", event });
        },
        onModeChange: (mode) => {
          dispatch({ type: "streamMode", mode });
        },
        onError: (streamError) => {
          const message = formatError(streamError);
          dispatch({ type: "setError", message });
          setError(message);
          setRunning(false);
        },
        onComplete: () => {
          dispatch({ type: "markComplete" });
          setRunning(false);
        },
        onReviewRequired: () => {
          setRunning(false);
        },
        buildExecutionRequest
      });
    } catch (runError) {
      const message = formatCustomRunError(runError);
      dispatch({ type: "setError", message });
      setError(message);
      setRunning(false);
    }
  }

  async function handleVerify() {
    if (runState.runId === null) {
      return;
    }

    setRunning(true);
    setError(null);

    try {
      const verificationResponse = await apiClient.verifyRun(runState.runId);
      dispatch({ type: "verificationUpdated", verification: verificationResponse });
    } catch (verificationError) {
      setError(formatError(verificationError));
    } finally {
      setRunning(false);
    }
  }

  async function handleTamper() {
    if (runState.runId === null) {
      return;
    }

    setRunning(true);
    setError(null);

    try {
      const tamperedVerification = await apiClient.tamperRun(runState.runId);
      dispatch({
        type: "verificationUpdated",
        verification: tamperedVerification,
        tamperedField: tamperedVerification.tampered_field ?? null
      });
      const verifiedAfterTamper = await apiClient.verifyRun(runState.runId);
      dispatch({
        type: "verificationUpdated",
        verification: verifiedAfterTamper,
        tamperedField: tamperedVerification.tampered_field ?? null
      });
    } catch (tamperError) {
      setError(formatError(tamperError));
    } finally {
      setRunning(false);
    }
  }

  async function handleReset() {
    eventsClientRef.current?.stop();
    setResetting(true);
    setRunning(false);
    setError(null);

    try {
      await apiClient.resetDemo();
      dispatch({ type: "reset" });
    } catch (resetError) {
      setError(formatError(resetError));
    } finally {
      setResetting(false);
    }
  }

  return (
    <AppShell
      workflowId={workflowLabel}
      runId={runState.runId}
      fallbackMode={runState.fallbackMode}
      decision={runState.decision?.value ?? null}
      onReset={handleReset}
      resetting={resetting}
      left={
        <>
          <ScenarioSwitcher
            scenarios={scenarios}
            activeScenario={runState.scenario}
            running={running}
            onRunScenario={handleRunScenario}
            onReset={handleReset}
          />
          <AgentProposalPanel proposal={runState.proposal} />
          <VultrStatusCard
            status={vultrStatus}
            loading={vultrLoading}
            error={vultrError}
            useVultr={useVultr}
            onToggleUseVultr={setUseVultr}
          />
          <CustomRunCard running={running} useVultr={useVultr} onRunCustom={handleRunCustom} />
        </>
      }
      center={
        <>
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
          <NaiveAgentStrip state={runState} />
          <ClearanceSpine state={runState} />
          <EventTimeline timeline={timeline} collapsed={runState.decision !== null} />
        </>
      }
      right={
        <>
          <div className="outcome-rail">
            <DecisionCard state={runState} />
            <ReviewerCard
              state={runState}
              loading={running}
              onReviewerIdChange={(reviewerId) => dispatch({ type: "setReviewReviewerId", reviewerId })}
              onReviewSubmitted={() => setRunning(true)}
              onError={setError}
            />
            <CounterfactualStrip
              counterfactual={runState.counterfactual}
              decision={runState.decision}
              amount={runState.proposal?.request.action.amount ?? null}
            />
          </div>
          <div className="enforcement-rail">
            <ClearanceTokenCard state={runState} />
            <MockBankExecutionCard state={runState} onAttemptExecution={handleAttemptExecution} />
          </div>
          <details className="system-drawer" data-testid="audit-drawer">
            <summary className="system-drawer__summary">Proof chain</summary>
            <div className="system-drawer__body">
              <ProofSeal state={runState} />
              <ProofPacketViewer state={runState} />
              <HashVerifier
                state={runState}
                onVerify={handleVerify}
                onTamper={handleTamper}
                onReset={handleReset}
                loading={running}
              />
              <SentinelMemoryCard state={runState} />
            </div>
          </details>
        </>
      }
    />
  );
}

function App() {
  return (
    <RunStoreProvider>
      <AppContent />
    </RunStoreProvider>
  );
}

export default App;
