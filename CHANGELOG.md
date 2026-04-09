# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.2.2] - 2026-04-09

### Added
- Runtime resilience and governance enhancements, including alerting, background queue execution, bulkhead isolation, hybrid executor support, query guards, quota guards, and query-result caching services.
- Operational tooling scripts for chaos probing, load/performance checks, and migration helpers.
- Concurrency regression test coverage (`tests/test_concurrency_regression.py`).

### Changed
- Updated core workflow, graph streaming, Neo4j integration, API surface, and schema/model definitions to support the new runtime controls and reliability features.
- Improved CI quality-gate checks for release readiness.

## [0.2.1] - 2026-04-09

### Added
- Runtime RAG/Agent operations controls:
  - retrieval profile control (`baseline` / `advanced` / `safe`)
  - canary routing and shadow traffic sampling
  - one-click rollback endpoint
  - AB compare / replay evaluation / benchmark trend APIs
- Session strategy lock APIs for consistent per-session retrieval behavior.
- Prompt versioning lifecycle with version list, approval, and rollback APIs.
- Index freshness tracking and admin freshness reporting endpoint.
- Production readiness checklist documentation.

### Changed
- Streaming response flow now supports overwrite-style updates (`answer_reset`) to avoid duplicated text after fallback/safety rewrite.
- Graph source cleanup now removes source-scoped `RELATED` edges during delete-by-source operations.
- Admin console and API contracts expanded for RAG/Agent ops governance.

### Fixed
- Fixed duplicated assistant output in stream mode when synthesis fallback occurs after partial chunks.
- Fixed stale graph edge residue after source-level index deletion.
- Corrected retrieval strategy schema note to include `safe`.

## [0.2] - 2026-04-08

### Added
- Admin operations overview API (`/admin/ops/overview`) and CSV export (`/admin/ops/export.csv`).
- Admin user provisioning flow (`/admin/users/create-admin`) with approval-token verification.
- Admin security actions for user password reset and admin approval-token reset.
- New readiness endpoint and related API coverage.
- New frontend admin operations dashboard, KPI views, trend charts, and CSV export action.
- New tests:
  - `tests/test_admin_ops_api.py`
  - `tests/test_admin_user_provisioning.py`
  - `tests/test_readiness_api.py`

### Changed
- Extended auth/user schema with creator metadata, ticket metadata, approval-token hash, and user classification fields.
- Improved audit log capabilities with richer filters and operational event classification.
- Expanded admin user-management flows (role/status/classification updates) across backend + frontend.
- Enhanced ingestion loaders for OCR/image extraction and text loading fallbacks.
- Updated query and document visibility logic to enforce user-scoped source access more consistently.

### Security
- Added stricter approval-token checks for privileged admin operations.
- Added stronger audit coverage for admin and auth-sensitive actions.

### Tests
- Expanded regression coverage for auth DB service, ingestion loaders, query intent, and agent resilience.

## [0.1.0] - 2026-04-08

### Added
- Initial public release.
- FastAPI backend + React frontend.
- Session, prompt, document upload/reindex/delete flows.
- User data isolation and retrieval allowlist protection.
- Admin file visibility controls (`private` / `public`).
- OCR configuration support with Tesseract.
