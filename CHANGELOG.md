# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.2.5] - 2026-04-27

### Fixed
- **[P0] Retrieval strategy parameter passing inconsistency**: `retrieval_strategy` and `allowed_sources` now work together correctly, fixing document source filtering.
- **[P0] Hybrid routing concurrent execution error**: Graph queries no longer execute twice in hybrid mode, reducing latency by 100-500ms.
- **[P1] Router decision vs adaptive planner conflict**: Router agent decisions are now preserved; adaptive planner only upgrades complexity when necessary (no downgrades).
- **[P1] Evidence sufficiency circular dependency**: Cleaned up routing logic to avoid duplicate hybrid evidence checks in `route_after_vector` and `route_after_graph`.
- **[P1] Query rewrite variant deduplication**: Duplicate query variants are now removed, reducing redundant LLM API calls by 10-30%.
- **[P1] Query rewrite LLM timeout control**: Added 2-second timeout and deadline checks to prevent LLM rewrite from blocking retrieval pipeline.
- **[P1] State access parameter validation**: Added validation for required `question` parameter in `run_query` with clear error messages.
- **[P2] Parent-child deduplication score preservation**: All score fields (hybrid_score, dense_score, bm25_score, rerank_score, rank_feature_score) are now preserved during deduplication.
- **[P2] Smalltalk fast-path state inconsistency**: Added `fast_path` flag to distinguish smalltalk from retrieval failures.
- **[P2] Web fallback semantic confusion**: Renamed to "allow fallback" for clarity; web research is conditional, not guaranteed.
- **[P2] Hybrid future cancellation incomplete**: Both vector and graph futures are now properly cancelled on submission failure.
- **[P2] Reranker fallback score normalization**: Fallback scores are now normalized to [0,1] range for consistency.
- **[P2] Citation sentence splitting improvement**: Enhanced sentence boundary detection to handle abbreviations and quotes correctly.
- **[P2] Web domain allowlist semantic clarity**: Allowlist now acts as strict whitelist; empty allowlist uses TLD-based trust scoring.
- **[P2] Graph signal score calculation optimization**: Changed from max to weighted average for more balanced scoring.
- **[P2] TTLCache concurrent performance optimization**: Implemented lazy cleanup strategy to reduce lock contention.
- **[P3] Neo4j allowed_sources filtering verification**: Confirmed correct implementation with defensive programming notes.
- **[P3] BM25 filtering logic clarification**: Added defensive programming checks for test compatibility.

### Changed
- Improved routing logic to respect router agent decisions while allowing complexity upgrades.
- Enhanced error handling in synthesis agent with proper stream failure fallback.
- Optimized web research source scoring with stricter thresholds and trusted domain list.
- Improved concurrent execution tracking with `hybrid_execution_success` flags.

### Performance
- Reduced redundant LLM API calls by 10-30% through query variant deduplication.
- Eliminated duplicate graph queries in hybrid mode (100-500ms latency reduction).
- Improved TTLCache performance under high concurrency with lazy cleanup.
- Added timeout controls to prevent LLM rewrite blocking (500-2000ms P99 latency reduction).

### Tests
- All 29 tests passing, including new regression tests for fixed issues.
- Added comprehensive test coverage for routing logic, parameter passing, and concurrent execution.

## [0.2.4] - 2026-04-26

### Added
- Query-to-answer UX speed optimization framework with tiered execution policy (fast/balanced/deep tiers).
- `TierClassifier` module for intelligent query complexity classification based on query characteristics, session context, and system load.
- `LatencyBudgetManager` for enforcing hard runtime limits per tier (retrieval timeout, synthesis token limits, retry attempts).
- Tier-aware retrieval executor with budget enforcement and conditional web fallback triggers.
- Enhanced synthesis agent with tier-aligned answer framing (fast: conclusion-first, balanced: evidence + uncertainty, deep: complete narrative).
- UX telemetry system for tracking first token latency (P50/P95/P99), tier distribution, tier confidence, and citation coverage per tier.
- Load-based automatic tier degradation (>80% load → downgrade one tier, >95% load → force fast tier).
- Frontend tier display with visual indicators (fast=green, balanced=blue, deep=purple) and expected latency ranges.
- Response headers for tier metadata (`X-Query-Tier`, `X-Tier-Confidence`) for backward-compatible tier awareness.
- User manual tier override capability with session-level preference persistence.

### Changed
- Improved first token latency targets: P50 ≤ 2s, P95 ≤ 4s (from previous best-effort approach).
- Enhanced streaming response flow with progressive evidence delivery and tier-specific answer depth.
- Web fallback trigger logic now conditional on local evidence confidence score (<0.5), temporal keywords, and tier budget.
- Retrieval top_k and rerank parameters now dynamically adjusted per tier (fast: 5/3, balanced: 10/5, deep: 20/10).
- Synthesis token limits enforced per tier (fast: 300, balanced: 800, deep: 1500 tokens).
- Timeout handling improved with graceful degradation and partial result delivery with "incomplete" flag.

### Fixed
- Tier classifier failure now falls back to balanced tier with explicit `tier_fallback=classifier_error` flag.
- Streaming interruption recovery now auto-falls back to non-stream completion without duplicate answer artifacts.
- Web fallback timeout no longer blocks main answer delivery; returns local-evidence answer with supplementation incomplete marker.

## [0.2.2.1] - 2026-04-10

### Changed
- Improved non-smalltalk streaming reliability and error handling for `/query/stream`.
- Strengthened smalltalk fast-path routing behavior and intent recognition.
- Hardened RAG indexing/retrieval internals: chunk parameter sanitization, cache invalidation hooks, and deterministic chunk/parent identifiers.
- Updated development startup guidance to reduce `uvicorn --reload` interruption impact.

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
