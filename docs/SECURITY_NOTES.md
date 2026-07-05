# Security Notes

## 1. Threats covered

- Prompt injection
- Bank account substitution
- Forged bank-change chain
- Duplicate invoice risk
- Missing evidence
- Tampered proof packet
- Unauthorized execution attempt
- Local secret leakage risk

## 2. Design controls

- Typed extraction boundary
- Deterministic gates
- Source spans
- Reality Gate
- ProofPacket hashes
- SHA-256 ledger
- HMAC clearance token
- Mock Bank token enforcement
- No frontend verdict logic
- No model verdict logic
- Env-only API keys
- TLS verification enabled
- No `verify=False`

## 3. Current limitations

- Mock Bank only
- Simulated tool calls
- Seeded demo documents
- No production auth or RBAC yet
- No persistent database yet
- No real payment rails
- No SOC 2 controls yet

## 4. Production roadmap

- Real ERP and AP integration
- Vendor master integration
- Bank ownership APIs
- Logistics APIs
- RBAC
- Persistent append-only ledger
- Audit exports
- SOC 2 controls
- Policy admin console
