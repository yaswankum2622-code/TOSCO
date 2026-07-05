# Live Vultr Serverless Inference Proof

**Trusted Orchestration & Settlement Clearance Operator**

Verified record of live Vultr integration testing for the RAISE Summit 2026 hackathon build.

> Vultr extracts structured fields. TOSCO deterministic gates decide. Mock Bank enforces the clearance token.

---

## Summary

| Item | Result |
|------|--------|
| **Test harness** | `backend/scripts/vultr_live_smoke.py` |
| **Overall status** | **PASSED** |
| **Vultr role** | Structured field extraction only |
| **TOSCO role** | Deterministic clearance after extraction |
| **Secrets** | Loaded from local `backend/.env` — never committed |

---

## What Was Tested

Three progressive levels validate the full integration path:

| Level | Test | Pass criteria |
|-------|------|---------------|
| **1** | Direct Vultr chat completion | Valid JSON response from `/v1/chat/completions` |
| **2** | Vultr extraction adapter | Structured fields returned matching invoice schema |
| **3** | TOSCO orchestrator (`use_vultr=true`) | Real Vultr extraction → deterministic gates → ALLOW |

---

## Safe Configuration

All live tests follow these rules:

| Rule | Detail |
|------|--------|
| Key source | `backend/.env` only — gitignored |
| Key in repo | Never — empty placeholders in `backend/.env.example` |
| Key in logs | Never printed |
| Authorization header | Never logged |
| TLS verification | Enabled — no `verify=False` |
| Trust store | `TOSCO_USE_SYSTEM_TRUST_STORE=true` (Windows-compatible) |
| Custom CA | Optional `VULTR_CA_BUNDLE` for corporate TLS inspection |

---

## Level 1 — Direct Chat Completion

```
[PASS] Level 1 direct Vultr chat completion worked
```

- Endpoint: Vultr Serverless Inference `/v1/chat/completions`
- Prompt: return exact JSON `{"status":"ok","provider":"vultr"}`
- Confirms: API key valid, TLS path working, response parseable

---

## Level 2 — Extraction Adapter

```
[PASS] Level 2 Vultr extraction adapter returned valid structured fields
```

- Input: seeded invoice + vendor master evidence
- Output: schema-valid fields — `invoice_id`, `vendor_name`, `amount`, `bank_account_last4`
- Confirms: structured JSON extraction boundary works end-to-end

---

## Level 3 — Full Orchestrator Integration

```
[PASS] Level 3 TOSCO orchestrator used real Vultr extraction and deterministic clearance succeeded
```

| Field | Value |
|-------|-------|
| `final_decision` | `ALLOW` |
| `token_issued` | `true` |
| `mock_bank_status` | `ACCEPTED` |

### Timeline events emitted

```text
VULTR_EXTRACTION_STARTED
VULTR_EXTRACTION_SUCCEEDED
… (gates, decision, token, proof, execution)
```

---

## Boundary Statement

```text
Vultr does NOT approve payment.
Vultr does NOT issue clearance tokens.
Vultr does NOT enforce execution.

Vultr extracts structured fields from document text.
TOSCO gates decide ALLOW / BLOCK / FREEZE.
Mock Bank enforces the HMAC clearance token.
```

---

## How to Reproduce

```powershell
cd backend
Copy-Item .env.example .env
# Add VULTR_API_KEY, VULTR_INFERENCE_URL, VULTR_MODEL to .env locally

.\.venv\Scripts\Activate.ps1
python scripts\vultr_live_smoke.py
```

Expected final line:

```text
LIVE VULTR SMOKE TEST PASSED
```

If response-shape parsing fails:

```powershell
python scripts\vultr_live_smoke.py --show-response-shape
```

See [`backend/scripts/README.md`](../backend/scripts/README.md) for TLS troubleshooting on Windows.

---

## Fallback Mode (When Vultr Unavailable)

When `VULTR_API_KEY` is unset:

- TOSCO uses local extraction fallback
- UI displays **LIVE FALLBACK** badge
- All deterministic gates run unchanged
- Demo remains fully functional without live inference

This is intentional — honest labeling, not silent degradation.

---

## Related Documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — Vultr integration architecture
- [`SECURITY_NOTES.md`](SECURITY_NOTES.md) — secret handling and threat model
- [`09_SECURITY_AND_THREAT_MODEL.md`](09_SECURITY_AND_THREAT_MODEL.md) — extraction sandbox isolation
