# Production Readiness Checklist

This checklist is for final go-live validation of the RAG/Agent system.

## 1) Infrastructure

- Neo4j is reachable from API host (`NEO4J_URI`, username/password verified).
- Vector store path is writable (`CHROMA_PERSIST_DIR`).
- Database path is writable (`APP_DB_PATH`).
- Optional Redis cache is reachable if `RETRIEVAL_CACHE_BACKEND=redis`.
- Optional model backends (Ollama/OpenAI) are reachable.

## 2) Config and Secrets

- `.env` exists on target host and is not committed to git.
- `OPENAI_API_KEY` is configured if OpenAI backend is used.
- `ADMIN_CREATE_APPROVAL_TOKEN_HASH` is configured (prefer hash over plain token).
- `RETRIEVAL_PROFILE` and SLO thresholds are explicitly set for production.
- Upload and OCR limits are reviewed for expected traffic.

## 3) API Health and Access

- `GET /health` returns `{"status":"ok"}`.
- `GET /ready` returns non-blocking services as expected.
- Non-admin user cannot access admin endpoints.
- Cross-user document/session visibility isolation is verified.

## 4) Retrieval and Agent Controls

- Retrieval profile switch works (`baseline/advanced/safe`).
- Canary config works and routing reason appears in debug metadata.
- Shadow sampling writes records (`/admin/ops/shadow/runs`).
- Session strategy lock works (`/sessions/{id}/strategy-lock`).
- One-click rollback resets runtime state to baseline.

## 5) Safety and Quality

- Evidence conflict marker appears when conflicting citations are injected.
- Grounding/support metrics are present in query debug fields.
- Prompt version approve/rollback APIs work for managed prompts.
- Replay trends can be generated from historical sessions.

## 6) Observability and Audit

- Audit logs are generated for admin/security-sensitive actions.
- Ops overview/alerts pages load with current KPIs.
- Index freshness report includes upload/reindex operations.
- Benchmark trend entries are persisted over multiple runs.

## 7) Frontend

- Frontend build succeeds (`npm run build`).
- Chat streaming works without duplicated answer text.
- Admin page tabs for Ops and RAG/Agent operations are fully functional.

## 8) Smoke Test (Suggested Sequence)

1. Login as admin and run `/ready`.
2. Upload a small document and verify retrieval with citations.
3. Switch retrieval profile and compare outputs via AB compare endpoint.
4. Enable canary + shadow, run several queries, verify logs and trends.
5. Trigger rollback and verify active profile and canary/shadow states reset.
