import { apiClient, buildApiUrl } from "./client";
import type {
  ContractRunEvent,
  ExecutionAttemptRequest,
  ExecutionAttemptResponse,
  RunSnapshotResponse
} from "./types";

interface EventSourceLike {
  close(): void;
  onerror: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent<string>) => void) | null;
}

interface RunEventsDependencies {
  createEventSource: (url: string) => EventSourceLike;
  getSnapshot: (runId: string) => Promise<RunSnapshotResponse>;
  attemptExecution: (payload: ExecutionAttemptRequest) => Promise<ExecutionAttemptResponse>;
}

export interface RunEventsHandlers {
  onEvent: (event: ContractRunEvent) => void | Promise<void>;
  onModeChange?: (mode: "sse" | "poll") => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
  onReviewRequired?: () => void;
  buildExecutionRequest: (snapshot: RunSnapshotResponse | null) => ExecutionAttemptRequest | null;
}

export interface RunEventsClient {
  start(runId: string, handlers: RunEventsHandlers): void;
  stop(): void;
}

const DEFAULT_DEPS: RunEventsDependencies = {
  createEventSource: (url) => new EventSource(url),
  getSnapshot: (runId) => apiClient.getRun(runId),
  attemptExecution: (payload) => apiClient.attemptExecution(payload)
};

function asError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }
  return new Error(String(error));
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function parseToken(rawToken: string | null): Record<string, unknown> | null {
  if (!rawToken) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawToken) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function inferEvidenceType(ref: string): string {
  if (ref.startsWith("invoice")) {
    return "invoice";
  }
  if (ref.startsWith("po")) {
    return "po";
  }
  if (ref.startsWith("grn")) {
    return "grn";
  }
  if (ref.startsWith("vendor-master")) {
    return "vendor_master";
  }
  if (ref.startsWith("policy-pack")) {
    return "policy_pack";
  }
  return "evidence";
}

function eventKey(event: ContractRunEvent): string {
  const data = event.data;
  switch (event.event) {
    case "EVIDENCE_RETRIEVED":
      return `${event.event}:${data["retrieval_pass"] ?? "0"}`;
    case "TOOL_CALLED":
      return `${event.event}:${data["tool_id"] ?? "tool"}`;
    case "GATE_STARTED":
    case "GATE_COMPLETED":
      return `${event.event}:${data["gate_id"] ?? "gate"}`;
    default:
      return event.event;
  }
}

function isTerminalSnapshot(snapshot: RunSnapshotResponse): boolean {
  return snapshot.status === "COMPLETED" || snapshot.status === "FAILED";
}

async function resolveExecutionRequest(
  runId: string,
  handlers: RunEventsHandlers,
  deps: RunEventsDependencies,
  snapshotHint: RunSnapshotResponse | null
): Promise<ExecutionAttemptRequest | null> {
  const directRequest = handlers.buildExecutionRequest(snapshotHint);
  if (directRequest !== null && directRequest.token !== null) {
    return directRequest;
  }

  const snapshot = snapshotHint ?? (await deps.getSnapshot(runId));
  return handlers.buildExecutionRequest(snapshot);
}

function snapshotToEvents(snapshot: RunSnapshotResponse): ContractRunEvent[] {
  const tokenPayload = parseToken(snapshot.clearance_token);
  const tokenId = stringValue(tokenPayload?.["token_id"]);
  const tokenRaw = snapshot.clearance_token;
  const expiresAt = stringValue(tokenPayload?.["expires_at"]);
  const proofHash = stringValue(tokenPayload?.["packet_hash"]);
  const eventTs = new Date(0).toISOString();
  const events: ContractRunEvent[] = [
    {
      event: "PLAN_STARTED",
      run_id: snapshot.run_id,
      ts: eventTs,
      data: {
        workflow_id: snapshot.workflow_id,
        workflow_name: snapshot.workflow_id
      }
    }
  ];

  snapshot.evidence_refs.forEach((ref, index) => {
    events.push({
      event: "EVIDENCE_RETRIEVED",
      run_id: snapshot.run_id,
      ts: eventTs,
      data: {
        retrieval_pass: index + 1,
        total_passes: snapshot.evidence_refs.length,
        evidence_type: inferEvidenceType(ref),
        evidence_types: snapshot.evidence_refs.map(inferEvidenceType),
        evidence_count: snapshot.evidence_refs.length,
        doc_id: ref
      }
    });
  });

  events.push({
    event: "EXTRACTION_STARTED",
    run_id: snapshot.run_id,
    ts: eventTs,
    data: {
      extractor: snapshot.fallback_mode ? "sandbox-fallback" : "vultr-serverless-inference",
      fallback_mode: snapshot.fallback_mode
    }
  });
  events.push({
    event: "EXTRACTION_SEALED",
    run_id: snapshot.run_id,
    ts: eventTs,
    data: {
      extraction_hash: snapshot.extraction_hash,
      fallback_mode: snapshot.fallback_mode
    }
  });

  snapshot.tool_calls.forEach((toolCall) => {
    events.push({
      event: "TOOL_CALLED",
      run_id: snapshot.run_id,
      ts: eventTs,
      data: {
        tool_id: toolCall.tool_id,
        simulated: toolCall.simulated,
        signal_keys:
          Array.isArray(toolCall.output?.signal_keys) &&
          toolCall.output.signal_keys.every((item) => typeof item === "string")
            ? toolCall.output.signal_keys
            : []
      }
    });
  });

  snapshot.gate_results
    .filter((gate) => gate.gate_id !== "G6_DECISION_SEAL")
    .forEach((gate) => {
      events.push({
        event: "GATE_STARTED",
        run_id: snapshot.run_id,
        ts: eventTs,
        data: {
          gate_id: gate.gate_id
        }
      });
      events.push({
        event: "GATE_COMPLETED",
        run_id: snapshot.run_id,
        ts: eventTs,
        data: {
          gate_id: gate.gate_id,
          status: gate.status,
          decision: gate.decision,
          reason_code: gate.reason_code,
          human_reason: gate.human_reason
        }
      });
    });

  if (snapshot.decision) {
    events.push({
      event: "DECISION_MADE",
      run_id: snapshot.run_id,
      ts: eventTs,
      data: {
        final_decision: snapshot.decision,
        status: snapshot.decision,
        allow_execution: snapshot.decision === "ALLOW",
        reason_codes: snapshot.gate_results.map((gate) => gate.reason_code)
      }
    });
  }

  if (snapshot.decision === "ALLOW" && tokenId && expiresAt) {
    events.push({
      event: "TOKEN_ISSUED",
      run_id: snapshot.run_id,
      ts: eventTs,
      data: {
        token_id: tokenId,
        expires_at: expiresAt,
        token: tokenRaw
      }
    });
  }

  if (snapshot.decision) {
    events.push({
      event: "PROOF_SEALED",
      run_id: snapshot.run_id,
      ts: eventTs,
      data: {
        proof_hash: proofHash,
        final_decision: snapshot.decision
      }
    });
  }

  events.push({
    event: "EXECUTION_ATTEMPTED",
    run_id: snapshot.run_id,
    ts: eventTs,
    data: {
      token_id: tokenId,
      amount: snapshot.intent?.action.amount ?? null,
      bank_account_last4: snapshot.intent?.action.bank_account_last4 ?? null
    }
  });

  return events;
}

export function createRunEventsClient(
  overrides: Partial<RunEventsDependencies> = {}
): RunEventsClient {
  const deps: RunEventsDependencies = {
    ...DEFAULT_DEPS,
    ...overrides
  };

  let activeSource: EventSourceLike | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;
  let terminalEventSeen = false;
  let seenKeys = new Set<string>();
  let processing: Promise<void> = Promise.resolve();

  function clearTimer(): void {
    if (pollTimer !== null) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function stop(): void {
    stopped = true;
    clearTimer();
    activeSource?.close();
    activeSource = null;
  }

  async function emitEvent(event: ContractRunEvent, handlers: RunEventsHandlers): Promise<void> {
    const key = eventKey(event);
    if (seenKeys.has(key)) {
      return;
    }

    let outgoingEvent = event;
    if (event.event === "EXECUTION_ATTEMPTED") {
      const executionRequest = await resolveExecutionRequest(event.run_id, handlers, deps, null);
      if (executionRequest !== null) {
        const result = await deps.attemptExecution(executionRequest);
        outgoingEvent = {
          ...event,
          data: {
            ...event.data,
            executed: result.executed,
            reason: result.reason
          }
        };
      }
    }

    seenKeys.add(key);
    await handlers.onEvent(outgoingEvent);
    if (event.event === "REVIEW_REQUIRED") {
      handlers.onReviewRequired?.();
    }
  }

  async function replaySnapshot(
    runId: string,
    handlers: RunEventsHandlers,
    snapshot: RunSnapshotResponse
  ): Promise<void> {
    const replay = snapshotToEvents(snapshot);
    for (const event of replay) {
      if (stopped || event.run_id !== runId) {
        return;
      }

      const key = eventKey(event);
      if (seenKeys.has(key)) {
        continue;
      }

      let outgoingEvent = event;
      if (event.event === "EXECUTION_ATTEMPTED") {
        const executionRequest = await resolveExecutionRequest(runId, handlers, deps, snapshot);
        if (executionRequest !== null) {
          const result = await deps.attemptExecution(executionRequest);
          outgoingEvent = {
            ...event,
            data: {
              ...event.data,
              executed: result.executed,
              reason: result.reason
            }
          };
        }
      }

      seenKeys.add(key);
      await handlers.onEvent(outgoingEvent);
    }
  }

  function startPolling(runId: string, handlers: RunEventsHandlers): void {
    activeSource?.close();
    activeSource = null;
    handlers.onModeChange?.("poll");

    const poll = async (): Promise<void> => {
      if (stopped) {
        return;
      }

      try {
        const snapshot = await deps.getSnapshot(runId);
        if (isTerminalSnapshot(snapshot)) {
          await replaySnapshot(runId, handlers, snapshot);
          handlers.onComplete?.();
          stop();
          return;
        }
      } catch (error) {
        handlers.onError?.(asError(error));
      }

      if (!stopped) {
        pollTimer = setTimeout(() => {
          void poll();
        }, 500);
      }
    };

    void poll();
  }

  function start(runId: string, handlers: RunEventsHandlers): void {
    stop();
    stopped = false;
    terminalEventSeen = false;
    seenKeys = new Set<string>();
    processing = Promise.resolve();

    const encodedRunId = encodeURIComponent(runId);
    const streamUrl = buildApiUrl(`/api/runs/${encodedRunId}/events`);

    if (typeof EventSource === "undefined") {
      startPolling(runId, handlers);
      return;
    }

    try {
      activeSource = deps.createEventSource(streamUrl);
      handlers.onModeChange?.("sse");
    } catch (error) {
      handlers.onError?.(asError(error));
      startPolling(runId, handlers);
      return;
    }

    activeSource.onmessage = (message) => {
      const parsed = JSON.parse(message.data) as ContractRunEvent;
      if (parsed.event === "EXECUTION_ATTEMPTED") {
        terminalEventSeen = true;
      }

      processing = processing
        .then(async () => {
          if (stopped) {
            return;
          }
          await emitEvent(parsed, handlers);
          if (parsed.event === "EXECUTION_ATTEMPTED") {
            handlers.onComplete?.();
            stop();
          }
        })
        .catch((error) => {
          handlers.onError?.(asError(error));
        });
    };

    activeSource.onerror = () => {
      if (stopped || terminalEventSeen) {
        return;
      }
      startPolling(runId, handlers);
    };
  }

  return {
    start,
    stop
  };
}
