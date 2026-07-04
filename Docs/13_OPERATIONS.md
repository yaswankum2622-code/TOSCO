# 13 — Operations

## Build order
1. Backend engine core (models, gate registry, decision fold, ledger) — **P0 — build first during the hackathon.**
2. Features (clearance token, counterfactual, evidence locker, auditor, sentinel, mock bank) — **P0 — build first during the hackathon.**
3. WorkflowDefinition loader + orchestrator emitting events.
4. API routes + SSE + SQLite persistence.
5. Seeds (clean/injection/forgery) + `/reset`.
6. React Clearance Terminal (event-driven UI per doc 07).
7. Vultr wiring (ExtractionSandbox → Serverless Inference; EvidenceProvider → VultronRetriever; fallback labels).
8. Reference AP Agent + NaiveAgentStrip + live-inject box.
9. Polish + record.

## Commit discipline
Public repo from commit #1. Push every 90 minutes (laptop-loss rule). One logical feature per commit. Protected `main`. CI runs pytest on gates + features. README carries the contribution statement ("concept prior, all code built at event").

## Environment variables
```
VULTR_API_KEY=...            # Serverless Inference + VultronRetriever
VULTR_INFERENCE_URL=...
TOSCO_TOKEN_SECRET=...        # HMAC signing key (never commit)
TOSCO_FALLBACK=false          # force local fallback for offline demo
DATABASE_URL=sqlite:///tosco.db
```

## Local run
```
# backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt   # fastapi uvicorn pydantic pyyaml pytest
uvicorn app.main:app --reload --port 8000
pytest -q                          # expect all green

# frontend
cd frontend && npm i && npm run dev  # Vite on :5173, proxy /api → :8000
```

## Fallback mode
If Vultr is unreachable, set `TOSCO_FALLBACK=true` (or auto-detect on error): local extraction/retrieval, `fallback_mode=true`, UI shows SANDBOX/FALLBACK. Determinism + all gates unchanged.

## Reset
`POST /api/reset` (or `make demo-reset`) wipes runs/ledger and reseeds in <30s. Run before every take.

## Demo recording checklist
- [ ] `pytest` green · [ ] `/reset` clean · [ ] fonts self-hosted (offline-safe) · [ ] SANDBOX badge visible · [ ] real Vultr call visible in log · [ ] two clean rehearsal runs · [ ] 60s video: clean → injection → forgery → proof · [ ] tamper→verify-fail shown · [ ] uploaded (YouTube/Loom) · [ ] submitted before deadline.

## Failure fallback plan
- SSE fights you → 500ms poll of `/api/runs/{id}`.
- VultronRetriever weak → local evidence store (labeled).
- Vultr inference flaky → cached extraction (labeled).
- Live-inject risky → keep the seeded injection beat.
- Anything stutters on camera → record after two clean runs; keep a recorded fallback clip.

## Cut if time is short (in order)
Drop tamper-demo → drop live-inject box → static counterfactual banner → SSE→polling. **Never cut:** gate engine, Reality-Gate FREEZE, clearance token + bank rejection, Proof Seal + live verify, injection beat.

## Final submission checklist
- [ ] Public repo, README with contribution statement + Vultr usage
- [ ] All 20 acceptance tests pass (doc 10)
- [ ] 60s demo video uploaded
- [ ] Submission form completed before **Sun 12:00 Paris / 15:30 IST** (target 14:30 IST buffer)
- [ ] Workflow YAML + bank-change skeleton in repo (extensibility proof)
