# Production Readiness Checklist

**Document Status**: Published  
**Version**: 2.0  
**Last Updated**: 2026-04-27  
**Audience**: Operations, Platform, Backend Engineering, Security  
**Scope**: Release and go-live validation for Multi-Agent Local RAG

Use this checklist before production launch, controlled pilot rollout, or formal team handoff.

## 1. Release Gate Summary

A deployment should not be marked production-ready unless all of the following are true:

- Core services start successfully
- Authentication and authorization boundaries are verified
- Retrieval and citation flows work with real documents
- Readiness, rollback, and basic observability are validated
- Configuration and secrets have been reviewed for the target environment

## 2. Infrastructure

| Check | Status |
| --- | --- |
| API host can reach `NEO4J_URI` |  |
| `CHROMA_PERSIST_DIR` is writable and persistent |  |
| `APP_DB_PATH` is writable and backed up appropriately |  |
| `SESSIONS_DIR` and `UPLOADS_DIR` exist with correct permissions |  |
| Redis is reachable if `RETRIEVAL_CACHE_BACKEND=redis` |  |
| Model backend endpoint is reachable and credentialed |  |
| Frontend build artifacts are available when serving from backend |  |

## 3. Configuration And Secrets

| Check | Status |
| --- | --- |
| `.env` is environment-specific and not committed |  |
| Only the intended model backend is enabled for the environment |  |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is present if required |  |
| `ADMIN_CREATE_APPROVAL_TOKEN_HASH` is configured for admin creation |  |
| `API_SETTINGS_ENCRYPTION_KEY` is configured for sensitive settings storage |  |
| Upload size and count limits are reviewed |  |
| OCR settings are reviewed if image/PDF ingestion is enabled |  |
| `API_BASE_URL_ALLOWLIST` reflects enterprise outbound policy |  |

## 4. Security And Access Control

| Check | Status |
| --- | --- |
| Non-admin users cannot access `/admin/*` endpoints |  |
| Cross-user document visibility isolation is verified |  |
| Cross-user session isolation is verified |  |
| Auth token TTL and failure limits match policy |  |
| Audit logs are generated for admin and auth-sensitive operations |  |
| Any plaintext bootstrap secret is removed after secure setup |  |

## 5. Functional Validation

| Check | Status |
| --- | --- |
| `GET /health` returns success |  |
| `GET /ready` reflects expected dependency state |  |
| `GET /metrics` is accessible as intended |  |
| Login and logout work end-to-end |  |
| Document upload succeeds |  |
| Reindex and delete flows succeed |  |
| Query endpoint returns grounded answers with citations |  |
| Streaming endpoint behaves correctly without duplicate output |  |
| Prompt approval and rollback flows behave correctly if used |  |

## 6. Retrieval And Runtime Controls

| Check | Status |
| --- | --- |
| Retrieval profile switching works |  |
| Canary configuration can be applied and observed |  |
| Rollback endpoint returns runtime state to baseline |  |
| Benchmark or replay flows run in the target environment if required |  |
| Caching behaves as expected for the configured backend |  |
| Tiered or adaptive retrieval behavior is acceptable for target workloads |  |

## 7. Observability And Operations

| Check | Status |
| --- | --- |
| Application logs are captured centrally or retained locally per policy |  |
| Readiness failures are actionable |  |
| Critical admin actions are auditable |  |
| Freshness or indexing signals can be reviewed by operators |  |
| Rollback procedure is documented and rehearsed |  |

## 8. Data And Recovery

| Check | Status |
| --- | --- |
| Data directories are included in backup scope as appropriate |  |
| Recovery procedure exists for app database and uploaded documents |  |
| Vector and graph stores can be rebuilt or restored within agreed objectives |  |
| Retention expectations for logs, sessions, and uploaded files are defined |  |

## 9. Suggested Smoke Test

1. Start backend and frontend.
2. Call `/health`, `/ready`, and `/metrics`.
3. Log in with a non-admin account.
4. Upload a small document and confirm it appears in the document list.
5. Run a query that should cite the uploaded content.
6. Confirm the answer streams correctly in the UI.
7. Verify the non-admin account cannot reach admin endpoints.
8. Log in as admin and validate retrieval profile and rollback controls.

## 10. Sign-Off

| Role | Name | Date | Decision |
| --- | --- | --- | --- |
| Engineering |  |  |  |
| Operations |  |  |  |
| Security |  |  |  |
| Product or Delivery |  |  |  |

## 11. Exit Criteria

The release is considered ready only when:

1. All blocking checks are complete.
2. Any accepted risks are documented explicitly.
3. Operational ownership for the environment is clear.
4. The rollback path has been validated.
