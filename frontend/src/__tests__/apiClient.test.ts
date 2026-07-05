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
      new Response(JSON.stringify({ status: "ok", service: "TOSCO", version: "0.1.0", mode: "demo", fallback_mode: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );

    await apiClient.getHealth();

    expect(fetch).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" }
      })
    );
  });

  it("startRun posts the scenario body", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          run_id: "run-clean-001"
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );

    await apiClient.startRun("clean");

    expect(fetch).toHaveBeenCalledWith(
      "/api/runs/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ scenario: "clean", use_vultr: false })
      })
    );
  });

  it("getVultrStatus calls the integration status endpoint", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          configured: false,
          base_url: "https://api.vultrinference.com/v1",
          model: "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
          mode: "serverless-inference",
          key_present: false
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );

    await apiClient.getVultrStatus();

    expect(fetch).toHaveBeenCalledWith(
      "/api/integrations/vultr/status",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" }
      })
    );
  });

  it("non-2xx responses throw ApiError", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error_code: "INVALID_SCENARIO", message: "Bad scenario" }), {
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
      "/api/runs/run-clean-001/verify",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" }
      })
    );
  });

  it("attemptExecution posts to the execution endpoint", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          executed: false,
          reason: "NO_TOKEN"
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );

    await apiClient.attemptExecution({
      run_id: "run-clean-001",
      token: null,
      vendor_id: "VEND-ACME-001",
      amount: 340000
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/execution/attempt",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          run_id: "run-clean-001",
          token: null,
          vendor_id: "VEND-ACME-001",
          amount: 340000
        })
      })
    );
  });
});
