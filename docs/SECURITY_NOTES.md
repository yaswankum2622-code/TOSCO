# TOSCO Security Notes

**Trusted Orchestration & Settlement Clearance Operator**

Security architecture for the hackathon build. This is a **demonstration system** — not production-hardened, not deployed to real banking rails.

---

## Security Thesis

> A clean-looking document chain should not be enough to move money.

TOSCO treats every LLM output as **untrusted input** until deterministic gates, external reality signals, and cryptographic proof confirm clearance.

| Principle | Implementation |
|-----------|----------------|
| Model extracts | Vultr returns schema-bound fields only |
| Gates decide | Python gate engine — no LLM verdict |
| Agent proposes | Reference AP agent never executes |
| Execution obeys | Mock Bank requires HMAC clearance token |
| Audit proves | SHA-256 hash-chained Proof Packet |

---

## Threat Model

### 1. Prompt injection (poisoned invoice / email)

| | |
|---|---|
| **Attack** | Hidden instructions in a document redirect payment to an attacker account |
| **Mitigation** | LLM extracts structured fields only; output is schema-validated and sealed; gates read typed fields, never raw model prose; G2/G3/G5 catch bank-account mismatch |
| **Demo outcome** | Naive agent APPROVES → TOSCO **BLOCK** → no token → Mock Bank rejected |
| **Status** | Demonstrated with seeded injection scenario |

### 2. Bank account substitution

| | |
|---|---|
| **Attack** | Invoice routes `$340,000` to account ending `0009` instead of verified vendor account |
| **Mitigation** | Reality Gate (G5) compares extracted bank details against vendor master; policy gate enforces registered account |
| **Demo outcome** | **BLOCK** · reason `NO_TOKEN` at bank |
| **Status** | Demonstrated |

### 3. Forged bank-change chain

| | |
|---|---|
| **Attack** | Internally consistent invoice + PO + GRN + bank-change letter — every document agrees |
| **Mitigation** | Reality Gate checks simulated external signals (bank-owner match, domain age, logistics); internal consistency alone cannot force ALLOW on high-risk change |
| **Demo outcome** | **FREEZE** · Sentinel records `BANK_ACCOUNT_MISMATCH` |
| **Status** | Demonstrated |

### 4. Duplicate invoice / missing evidence

| | |
|---|---|
| **Attack** | Re-submit or omit required documents |
| **Mitigation** | G1 Evidence Gate · G4 Risk Gate · simulated duplicate-invoice tool |
| **Demo outcome** | Deterministic BLOCK or FREEZE based on policy |
| **Status** | Gate logic tested (204 backend tests) |

### 5. Unauthorized execution (agent bypass)

| | |
|---|---|
| **Attack** | Compromised agent calls payment rail without clearance |
| **Mitigation** | Mock Bank requires valid HMAC token bound to `vendor_id + amount + ledger_head`; no token → `NO_TOKEN` |
| **Demo outcome** | `EXECUTION_REJECTED` in event log |
| **Status** | Demonstrated |

### 6. Tampered proof packet

| | |
|---|---|
| **Attack** | Alter sealed decision or amount after the fact |
| **Mitigation** | SHA-256 hash chain; any edit breaks subsequent links; live `/verify` endpoint |
| **Demo outcome** | Tamper demo → verify **FAILED** · tampered field surfaced in UI |
| **Status** | Demonstrated |

### 7. Clearance token theft / replay

| | |
|---|---|
| **Attack** | Steal, edit, or reuse a token |
| **Mitigation** | HMAC-SHA256 signature · bound to vendor + amount + ledger head · short expiry · non-ALLOW never receives token |
| **Demo outcome** | Mock Bank rejects mismatched or tampered tokens |
| **Status** | Unit tested |

### 8. Secret leakage

| | |
|---|---|
| **Attack** | API keys committed to repo, logs, or UI |
| **Mitigation** | Keys in `backend/.env` only (gitignored) · never logged · never in frontend · TLS verification enabled · no `verify=False` |
| **Status** | Enforced in codebase and `.gitignore` |

---

## Design Controls

```text
┌─────────────────────────────────────────────────────────┐
│  Untrusted zone          │  Trusted zone                │
│  · LLM extraction        │  · Gate engine (Python)      │
│  · Agent proposal        │  · Decision fold             │
│  · User custom input     │  · HMAC token signing        │
│                          │  · SHA-256 ledger            │
│                          │  · Mock Bank enforcement     │
└─────────────────────────────────────────────────────────┘
```

| Control | Detail |
|---------|--------|
| Typed extraction boundary | Pydantic-validated schema; sealed before gates |
| Deterministic gates | G1–G6 plugins; no model in decision path |
| Source spans | Groundedness gate traces fields to evidence |
| Reality Gate | External signals vs. document claims |
| Proof Packet | Evidence hashes only — no raw document bodies in proof |
| SHA-256 ledger | Tamper-evident append-only chain |
| HMAC clearance token | `hmac.compare_digest` · constant-time compare |
| Mock Bank enforcement | Mechanical token check — not procedural trust |
| No frontend verdict logic | UI displays backend events only |
| No model verdict logic | Vultr extracts; gates decide |
| Env-only secrets | `VULTR_API_KEY` from environment · never in repo |
| TLS | System trust store + optional `VULTR_CA_BUNDLE` |

---

## What Vultr Does NOT Do

| Vultr does | Vultr does not |
|------------|----------------|
| Extract structured fields from document text | Approve or block payments |
| Return latency and model metadata | Issue clearance tokens |
| Fall back honestly when unavailable | Enforce execution at Mock Bank |
| | Decide ALLOW / BLOCK / FREEZE |

---

## Sandbox Boundaries (Honest Labeling)

This hackathon build is explicitly sandboxed:

- **Mock Bank** — no real wires, no real payment rails
- **Seeded evidence** — demo documents, not live ERP
- **Simulated tools** — policy/risk/domain signals are demo adapters
- **In-memory state** — no persistent production database
- **No RBAC / SSO** — no enterprise identity layer yet

All demo screens carry **LIVE SANDBOX** or **LIVE FALLBACK** labeling.

---

## Secret Handling

```powershell
# Setup (never commit .env)
cd backend
Copy-Item .env.example .env
# Add VULTR_API_KEY locally only
```

| Rule | Status |
|------|--------|
| `.env` gitignored | ✓ |
| `backend/.env.example` has empty placeholders | ✓ |
| No keys in README, docs, tests, or screenshots | ✓ |
| Authorization header never logged | ✓ |
| Rotate key immediately if exposed | Documented in `backend/scripts/README.md` |

---

## Verification Checklist

| Check | Command |
|-------|---------|
| No `.env` tracked | `git ls-files \| findstr .env` → empty |
| No key literals | `git grep VULTR_API_KEY=` → example files only |
| Backend security tests | `cd backend && python -m pytest -q` |
| Tamper demo | Run forgery/clean scenario → tamper → verify fails |
| Token enforcement | BLOCK scenario → Mock Bank shows `NO_TOKEN` |

---

## Related Documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system design and crypto contracts
- [`LIVE_VULTR_PROOF.md`](LIVE_VULTR_PROOF.md) — live inference verification record
