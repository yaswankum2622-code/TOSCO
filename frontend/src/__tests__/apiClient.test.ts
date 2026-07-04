import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiClient } from "../api/client";

describe("apiClient", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getHealth calls /api/health", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", service: "TOSCO", version: "0.1.0", mode: "demo" }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );

    await apiClient.getHealth();

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/health",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" }
      })
    );
  });

  it("startRun posts the scenario body", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          scenario: "clean",
          run_id: "run-clean-001",
          final_decision: "ALLOW",
          allow_execution: true,
          token_issued: true,
          mock_bank_status: "ACCEPTED",
          mock_bank_reason_code: "EXECUTION_ACCEPTED",
          proof_hash: "a".repeat(64),
          ledger_entry_hash: "b".repeat(64),
          timeline_events_count: 12
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );

    await apiClient.startRun("clean");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/runs/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ scenario: "clean" })
      })
    );
  });

  it("non-2xx responses throw ApiError", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: "INVALID_SCENARIO", detail: "Bad scenario" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
        statusText: "Bad Request"
      })
    );

    await expect(apiClient.startRun("unknown")).rejects.toEqual(new ApiError(400, "Bad scenario"));
  });

  it("verifyRun calls the verify endpoint", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          run_id: "run-clean-001",
          ledger_chain_valid: true,
          packet_entry_valid: true,
          proof_hash: "a".repeat(64),
          ledger_entry_hash: "b".repeat(64),
          verified: true
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );

    await apiClient.verifyRun("run-clean-001");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/runs/run-clean-001/verify",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" }
      })
    );
  });
});
