import type {
  EventTimelineResponse,
  HealthResponse,
  ProofPacketResponse,
  ResetResponse,
  RunSummaryResponse,
  ScenarioMetadata,
  StartRunRequest,
  VerifyRunResponse,
  VultrStatusResponse,
  WorkflowMetadata
} from "./types";

const FALLBACK_API_BASE_URL = "http://127.0.0.1:8000";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? FALLBACK_API_BASE_URL).replace(/\/+$/, "");

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
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = response.statusText || "Request failed";

    try {
      const errorPayload = (await response.json()) as { detail?: string; error?: string };
      message = errorPayload.detail ?? errorPayload.error ?? message;
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
  startRun: (scenario: string, useVultr?: boolean) =>
    requestJson<RunSummaryResponse>("/api/runs/start", {
      method: "POST",
      body: JSON.stringify({
        scenario,
        use_vultr: useVultr ?? false
      } satisfies StartRunRequest)
    }),
  listRuns: () => requestJson<RunSummaryResponse[]>("/api/runs"),
  getRun: (runId: string) => requestJson<RunSummaryResponse>(`/api/runs/${runId}`),
  getEvents: (runId: string) => requestJson<EventTimelineResponse>(`/api/runs/${runId}/events`),
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

export { apiBaseUrl, requestJson };
