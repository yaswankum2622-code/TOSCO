import type {
  AgentProposeRequest,
  AgentProposeResponse,
  ExecutionAttemptRequest,
  ExecutionAttemptResponse,
  HealthResponse,
  ProofPacketResponse,
  ResetResponse,
  RunHandleResponse,
  RunSnapshotResponse,
  RunSummaryResponse,
  ScenarioMetadata,
  StartRunRequest,
  CustomRunRequest,
  VerifyRunResponse,
  VultrStatusResponse,
  WorkflowMetadata
} from "./types";

const apiBase = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

function buildApiUrl(path: string): string {
  return `${apiBase}${path}`;
}

type JsonRequestOptions = RequestInit & {
  body?: BodyInit | null;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(path: string, options: JsonRequestOptions = {}): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = response.statusText || "Request failed";

    try {
      const errorPayload = (await response.json()) as {
        message?: string;
        detail?: string;
        error?: string;
      };
      message = errorPayload.message ?? errorPayload.detail ?? errorPayload.error ?? message;
    } catch {
      // Fall back to the status text when the response body is not JSON.
    }

    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  getHealth: () => requestJson<HealthResponse>("/api/health"),
  getVultrStatus: () => requestJson<VultrStatusResponse>("/api/integrations/vultr/status"),
  getWorkflows: () => requestJson<WorkflowMetadata[]>("/api/workflows"),
  getScenarios: () => requestJson<ScenarioMetadata[]>("/api/scenarios"),
  proposeIntent: (payload: AgentProposeRequest) =>
    requestJson<AgentProposeResponse>("/api/agent/propose", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  startRun: (scenario: string, useVultr?: boolean) =>
    requestJson<RunHandleResponse>("/api/runs/start", {
      method: "POST",
      body: JSON.stringify({
        scenario,
        use_vultr: useVultr ?? false
      } satisfies StartRunRequest)
    }),
  startCustomRun: (payload: CustomRunRequest) =>
    requestJson<RunHandleResponse>("/api/runs/custom", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listRuns: () => requestJson<RunSummaryResponse[]>("/api/runs"),
  getRun: (runId: string) => requestJson<RunSnapshotResponse>(`/api/runs/${runId}`),
  attemptExecution: (payload: ExecutionAttemptRequest) =>
    requestJson<ExecutionAttemptResponse>("/api/execution/attempt", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getProof: (runId: string) => requestJson<ProofPacketResponse>(`/api/runs/${runId}/proof`),
  verifyRun: (runId: string) => requestJson<VerifyRunResponse>(`/api/runs/${runId}/verify`),
  tamperRun: (runId: string) =>
    requestJson<VerifyRunResponse>(`/api/runs/${runId}/tamper-demo`, {
      method: "POST"
    }),
  resetDemo: () =>
    requestJson<ResetResponse>("/api/reset", {
      method: "POST"
    })
};

export { apiBase, buildApiUrl, requestJson };
