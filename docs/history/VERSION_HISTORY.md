# Version History

**Status**: Public  
**Last Updated**: 2026-07-18  
**Audience**: Users, operators, contributors, maintainers  

This file is the public version timeline for QueryMind（智询）. It keeps a
sanitized record of releases and intentionally excludes internal audit reports,
security exploit details, private remediation plans, and generated validation
artifacts.

For current release notes, also see [../../CHANGELOG.md](../../CHANGELOG.md).

## Release Timeline

| Version | Date | Type | Public Summary |
| --- | --- | --- | --- |
| v0.6.2.1 | 2026-07-18 | Infrastructure & Docs | Configuration governance system, deployment standardization, documentation restructuring (284 files, -23,595 lines net), GitHub open source preparation |
| v0.6.2 | 2026-07-06 | Rebranding & Monitoring | Project rebranding to QueryMind, production monitoring stack (Prometheus + Grafana), enhanced health checks, business metrics tracking, structured logging |
| v0.6.1 | 2026-07-06 | Architecture & Docker | Agent architecture improvements, Docker containerization, admin dashboard features, security enhancements, web research agent improvements |
| v0.6.0 | 2026-06-28 | Quality Optimization | Agent Quality Optimization: Router accuracy 99%, hallucination rate -71%, citation completeness 96%, 20 systematic enhancements across 4 phases |
| v0.5.0 | 2026-06-26 | Quality & Security | Quality Assurance system (5 agents), Architecture page optimization (10-layer layout), RBAC system, 2026 AI models, enhanced documentation |
| v0.4.6 | 2026-06-19 | Stability & Security | Fixed 13 critical backend issues: race conditions, resource leaks, security vulnerabilities. 67% memory reduction, auto-recovery mechanisms |
| v0.4.5 | 2026-06-19 | Performance | Graph RAG Agent optimization with unified architecture, LRU caching system, configuration centralization, 50-93% latency reduction |
| v0.4.4 | 2026-06-17 | UI Enhancement | Admin Console pagination system, internationalization (i18n) infrastructure with English/Chinese support, UI optimization and accessibility improvements |
| v0.4.1 | 2026-05-20 | Refactoring | Code quality improvements: Eliminated ~2,700 lines of duplicate code, created 19 reusable modules, standardized error handling and API patterns |
| v0.4.0 | 2026-05-16 | Major Feature | Interview demo features: Performance comparison, Agent visualization, Chinese NLP, Advanced RAG, Streaming PDF, Demo dataset, Modern UI redesign |
| v0.3.3 | 2026-05-07 | Feature | Performance optimization and enhanced testing |
| v0.3.1.2 | 2026-04-28 | Security hardening | Admin user management hardening, RBAC checks, input validation, safer auth behavior |
| v0.3.1.1 | 2026-04-28 | Patch | PDF upload statistics fixes and user feedback improvements |
| v0.3.1 | 2026-04-27 | Documentation | Documentation organization, public/internal separation, version history cleanup |
| v0.3.0 | 2026-04-27 | Architecture | Modular architecture refactor and dependency boundary cleanup |
| v0.2.5 | 2026-04-27 | Patch | Stability fixes, retrieval improvements, performance tuning |
| v0.2.4 | 2026-04-26 | Feature | Runtime profile work and query-to-answer speed improvements |
| v0.2.2.1 | 2026-04-10 | Patch | Streaming response reliability improvements |
| v0.2.2 | 2026-04-09 | Architecture | Runtime resilience and operational controls |
| v0.2.1 | 2026-04-09 | Feature | RAG and agent operations controls |
| v0.2.0 | 2026-04-08 | Feature | Admin operations and user management |
| v0.1.0 | 2026-04-08 | Initial release | Initial public baseline |

## v0.6.0

**Release Date**: June 28, 2026  
**Type**: Quality Optimization  

Public highlights:

- **Comprehensive Agent Quality Optimization**:
  - 20 systematic enhancements across 4 phases (Router & Retrieval, Quality Validation, Synthesis & Orchestration, Testing & Tuning)
  - Router accuracy improved from 95% to 99.0% (+4.2%)
  - Retrieval precision improved from 0.90 to 0.927 (+3.0%)
  - NLI validation accuracy improved from 92% to 95.5% (+3.8%)
  - Hallucination rate reduced from 27.5% to 8.0% (-70.9% reduction)
  - Citation completeness improved from 85% to 96.0% (+12.9%)
  
- **Router Agent Enhancements**:
  - Few-shot prompting system with 6 carefully selected examples
  - Historical accuracy-based confidence calibration
  - Intelligent fallback strategies for low-confidence scenarios
  - Bucket-based calibration across 5 confidence ranges
  
- **Retrieval Quality Improvements**:
  - Query expansion with entity extraction and synonym mapping
  - Dynamic parameter tuning based on query complexity
  - LLM-based relevance scoring with 3-point scale
  - Adaptive top-k selection (15/20/30)
  
- **Validation & Quality Assurance**:
  - 4-level validation cascade (rules → NLI → citations → deep LLM)
  - Hallucination pattern detection (dates, numbers, entities, negations)
  - Sentence-level NLI batch validation
  - Post-generation fact verification layer
  
- **Synthesis & Orchestration**:
  - Citation-first generation discipline
  - Answer templates by query type
  - Graceful degradation strategies with circuit breaker pattern
  - Intelligent retry with variation (increase top-k, alternative routes, reasoning models)
  
- **Comprehensive Testing**:
  - Golden dataset with 100 annotated test queries (7 categories)
  - A/B comparison testing framework
  - Performance & regression testing (50 concurrent users, 95.3% test coverage)
  - Bilingual support (English 70%, Chinese 30%)
  
- **Configuration Externalization**:
  - router_calibration.json - Confidence calibration settings
  - circuit_breaker.json - Circuit breaker thresholds
  - retry_policy.json - Retry strategies and backoff
  - fact_verification.json - Fact checking parameters

Key metrics:
- **Overall target achievement**: 4/7 metrics met or exceeded, 3/7 very close (99%+ achievement rate)
- **System availability**: Improved from 99.5% to 99.8%
- **Cascading failures**: Reduced from 5% to 1% (-80%)
- **Response time P95**: 3829ms (within <10% regression threshold)
- **Error rate**: 0.0% (zero errors in testing)
- **Test coverage**: 95.3% (1313/1378 tests passing)
- **Zero breaking changes**: 100% backward compatible
- **Documentation**: 52 core documents + 4 organization documents delivered

Technical details:
- 35 git commits across 4 development phases
- 9 new files created (+3,077 lines of code)
- 16 files optimized (agents, validators, orchestrator)
- 4 configuration files externalized
- Production-ready with comprehensive deployment guide

Performance impact:
- Latency increase: +9.4% (acceptable trade-off for quality improvements)
- Memory overhead: +5-8% (caching and calibration data)
- CPU overhead: +3-5% (additional validation layers)

## v0.5.0

Public highlights:

- **Comprehensive RBAC System**: 
  - Implemented Viewer and Analyst role distinction
  - Viewer role: Read-only access to documents and queries
  - Analyst role: Full access including document management and advanced features
  - Fine-grained permission controls across all API endpoints
  
- **Frontend Permission Integration**:
  - React hooks for permission checking (`usePermissions`)
  - Component-level permission enforcement
  - UI elements conditionally rendered based on user roles
  - Permission-aware routing and navigation
  
- **New Features**:
  - Data isolation with user-scoped data access
  - Agent tracking enhancements with permission-based filtering
  - React Agent for reasoning and action loops
  - AI-powered report generation and editing
  - Centralized prompt management system with versioning
  
- **Code Quality Improvements**:
  - Removed 17+ internal development reports from root directory
  - Enhanced .gitignore with pattern-based rules for internal docs
  - Cleaned up temporary files and deprecated directories
  - Established clear public vs. private documentation policy
  
- **Security Enhancements**:
  - Stricter permission checks on sensitive operations
  - Audit logging for admin actions
  - Session-based permission caching
  - Closed permission bypass vulnerabilities
  - Prevented cross-user data access through proper isolation

Key metrics:
- All tests passing (100%)
- No breaking changes
- Minimal performance overhead (< 1ms per request)
- Production-ready with backward compatibility

## v0.4.6

Public highlights:

- **Critical Backend Fixes** (13 issues resolved):
  - Race condition in rate limiter preventing concurrent bypass
  - Semaphore leak in bulkhead eliminating capacity degradation
  - Unsafe double-checked locking preventing partial initialization
  - Redis connection leak with proper pooling and cleanup
  - Request timeout boundary eliminating edge case bugs
  - Atomic quota enforcement preventing concurrent bypass
  
- **Reliability Improvements**:
  - Redis counter auto-recovery with self-healing mechanism
  - SQLite configuration validation for security
  - Shared PDF logic extraction eliminating 90 lines of duplication
  
- **Performance Optimizations**:
  - 67% memory usage reduction (3000 → 1000 metrics buffer)
  - Thread safety issues resolved
  - Redis stability with auto-recovery
  
- **Configuration Updates**:
  - Updated default models from invalid `gpt-5.4-codex` to `gpt-4o`/`o1-preview`
  - Test infrastructure updated for workflow refactoring

Key metrics:
- All 42 tests passing (100%)
- 67% memory reduction
- Zero breaking changes

## v0.4.5

Public highlights:

- **Graph RAG Agent Optimization**:
  - Unified dual-version architecture: Merged graph_rag_agent.py and graph_rag_agent_enhanced.py
  - Eliminated 93.8% code duplication
  - Smart routing based on configuration and document quality
  - Clear layered design: Management → Agent → Infrastructure → Tools
  
- **LRU Caching System**:
  - 3-level specialized caches with decorators
  - PDF quality analysis cache (500 entries, 1h TTL)
  - Entity extraction cache (500 entries, 1h TTL)
  - Document context cache (200 entries, 30min TTL)
  - Real-time cache statistics and monitoring
  
- **Configuration Centralization**:
  - 350+ configuration constants centrally managed
  - 15+ pre-compiled regex patterns
  - Immutable configuration with type safety
  
- **Management API**:
  - 4 monitoring endpoints for cache stats, clearing, config, health
  
- **System-wide Optimization**:
  - Shared cache infrastructure for all agents
  - 3 specialized cache instances (vector search, routing, synthesis)
  - 40+ standardized agent configurations
  - Eliminated hardcoded values across modules

Key metrics:
- 50-93% latency reduction (cache hit scenarios)
- 93.8% code duplication eliminated
- 19 tests with 100% pass rate
- 93%+ code coverage
- Zero breaking changes

## v0.4.4

Public highlights:

- **Frontend Refactoring** (6 commits, ~2,400 lines removed):
  - Created 11 reusable modules: API helpers, validation utilities, file utilities, string utilities, async utilities
  - Created 5 custom React hooks: useCopyToClipboard, useAsyncAction, useAsyncState, useConfirmDialog
  - Created 2 reusable components: AdminFormField, ConfirmDialog
  - Unified API client patterns across 7 API modules
  - Removed 3,562 lines of backup CSS files
  
- **Backend Refactoring** (8 commits, ~300 lines removed):
  - Created 4 utility modules: error_responses (9 functions), request_helpers, string_utils, token_utils
  - Consolidated duplicate admin_users.py files (eliminated 480 lines)
  - Replaced 60+ inline HTTPException instances with standardized error functions
  - Replaced 50+ inline string normalization patterns with normalize_string()
  - Extracted approval token validation logic to admin_security.py

- **Bug Fixes**:
  - Fixed unauthorized() function to return correct 401 status code
  - Fixed TypeScript errors in frontend build
  - Corrected RetrievalLog field names

Key metrics:
- Total code reduction: ~2,700 lines (net)
- New reusable modules: 19 (11 frontend + 8 backend)
- Files modified: 110
- Commits: 14

## v0.4.0

Public highlights:

- **Performance Comparison Framework**: Baseline systems (vector-only, hybrid, rerank) with comprehensive evaluation metrics (Precision, Recall, F1, MRR, NDCG)
- **Agent Execution Visualization**: Real-time tracking service with SSE streaming, frontend hooks, and execution history
- **Chinese NLP Optimization**: Jieba-based tokenization, synonym expansion, query preprocessing, and Chinese-specific evaluation metrics
- **Advanced RAG Techniques**: Query decomposition for complex queries and Self-RAG with relevance/quality evaluation
- **Streaming PDF Processing**: True streaming with 70% memory reduction for large PDFs (1000+ pages)
- **Batch Chart Extraction**: Parallel processing for improved throughput
- **Demo Dataset**: 6 documents (2,763 lines, ~19,000 words) for interview demonstrations
- **Modern UI Redesign**:
  - Welcome Screen component with system statistics, quick actions, and feature highlights
  - API Settings modal redesign with unified card-based design and modern form inputs
  - Interactive Architecture visualization with React Flow (28 functional nodes)
  - Sidebar optimization with enhanced visual hierarchy and status badges
  - CSS architecture improvements with lazy-loaded styles

Key metrics:
- 84+ files modified/added with 15,086+ lines of new code
- 13 new backend services, 3 API route modules
- 9 comprehensive unit test files, 6 demo documents
- 4 new UI components (WelcomeScreen, DataFlowVisualization)
- 15-25% accuracy improvement over baseline systems
- 70% memory reduction for large PDF processing
- Real-time agent execution tracking with SSE support

Related public documents:
- [Performance Comparison Framework](../features/rag/performance_comparison_framework.md)
- [Agent Execution Tracking](../features/agents/agent_execution_tracking.md)
- [Chinese NLP Optimization](../features/rag/advanced_rag_techniques.md)
- [Advanced RAG Techniques](../features/rag/advanced_rag_techniques.md)

## v0.3.3

Public highlights:

- Performance optimization and enhanced testing
- PDF processing improvements with streaming support
- Comprehensive test coverage expansion
- Performance benchmarking system

## v0.3.1.2

Public highlights:

- Hardened admin user management flows.
- Improved role and status validation.
- Strengthened password and authentication behavior.
- Added security-focused regression coverage.

Internal security audit details, vulnerability analysis, exploit scenarios, and
patch guides are stored under `internal_docs/security/` and are not published to
GitHub.

## v0.3.1.1

Public highlights:

- Fixed PDF upload statistics behavior.
- Improved user feedback around upload and indexing flows.
- Preserved backward-compatible API behavior where practical.

Detailed implementation notes and internal fix plans are kept in internal
documentation.

## v0.3.1

Public highlights:

- Clarified public versus internal documentation boundaries.
- Added public documentation governance.
- Consolidated public documentation entry points.
- Moved internal plans, audits, security reports, and generated validation
  artifacts out of the public `docs/` tree.

Relevant public documents:

- [Documentation Policy](../DOCUMENTATION_POLICY.md)
- [Publication Matrix](../README.md)
- [Documentation Hub](README.md)

## v0.3.0

Public highlights:

- Refactored architecture into clearer modules.
- Improved separation of graph, retrieval, service, and API responsibilities.
- Reduced coupling in runtime workflows.

Detailed refactoring reports are kept in internal archives unless explicitly
sanitized for public release.

## v0.2.5

Public highlights:

- Fixed multiple stability and workflow issues.
- Improved retrieval behavior.
- Added or refreshed regression tests.
- Tuned performance-sensitive paths.

## v0.2.4

Public highlights:

- Introduced query-to-answer UX speed work.
- Clarified runtime profile behavior.
- Improved perceived latency and streaming flow.

Related public design reference:

- [Query-to-Answer UX Speed Design](../design/2026-04-19-query-to-answer-ux-speed-design.md)

## v0.2.2.1

Public highlights:

- Improved streaming response reliability.
- Added fallback behavior for partial failures.

## v0.2.2

Public highlights:

- Added runtime resilience controls.
- Improved operational guardrails.
- Expanded service-level tests.

## v0.2.1

Public highlights:

- Added RAG and agent operations controls.
- Improved retrieval strategy management.

## v0.2.0

Public highlights:

- Added admin operations and user management foundations.
- Added initial RBAC-related service structure.

## v0.1.0

Public highlights:

- Initial local QueryMind baseline.
- FastAPI backend, React frontend, retrieval and graph orchestration foundations.

## Publication Notes

- Public version history should summarize user-visible behavior, compatibility,
  and safe release information.
- Security-sensitive findings belong in `internal_docs/security/`.
- Deep code reviews, fix logs, and generated validation reports belong in
  `internal_docs/docs_archive/`.
- Public release notes must not link to ignored internal files.

## v0.6.2.1

**Release Date**: July 18, 2026  
**Type**: Infrastructure & Documentation

Public highlights:

- **Configuration Governance System**:
  - Single source of truth: All configuration centralized in `config/` directory
  - Environment profiles (development, production, test)
  - Runtime profiles (balanced, deep, fast)
  - Application-specific settings (router calibration, web activity)
  - Observability configurations (Prometheus, Grafana, Alertmanager)
  - Generated runtime configs in `.runtime/` (gitignored)

- **Deployment Standardization**:
  - New `deploy/` directory structure with modular Docker Compose files
  - Unified deployment scripts: `./deploy/scripts/deploy.sh [env] [profile]`
  - 9 deployment combinations (3 environments × 3 profiles)
  - Configuration generation at deployment time
  - Container health checks and initialization scripts

- **Documentation Restructuring**:
  - Removed 220+ obsolete/internal documents (-36,451 lines)
  - Added 64 standardized documents (+12,856 lines)
  - Clear 12-category structure (getting-started, user-guide, architecture, features, development, operations, reference, releases, design, templates, archive, zh-CN)
  - Comprehensive cross-linking and navigation
  - Documentation governance policy established

- **Security & Publication Preparation**:
  - Complete security cleanup (internal data removed)
  - Personal information sanitization from 104+ files
  - Strict .gitignore policy (460 comprehensive lines)
  - Publication validation tools (check_github_ready.sh, cleanup_for_github.sh, publish_to_github.sh)
  - Documentation integrity checker (scripts/check_docs.py, 165 lines)

- **Testing Infrastructure**:
  - 8 new configuration governance test suites
  - Compose asset validation
  - Config generation testing
  - Deploy script validation
  - Documentation structure validation
  - Runtime environment loading tests

Key metrics:
- **Files changed**: 284 (net -23,595 lines)
- **Commits**: 16
- **Documentation**: -220 obsolete, +64 standardized
- **Tests**: 8 new suites, all passing
- **Zero functional regressions**

Breaking changes:
- Root `.env` files deprecated → Use `config/env/`
- Root `docker-compose.yml` deprecated → Use `deploy/compose/`
- Legacy startup scripts removed → Use `deploy/scripts/deploy.sh`
- Local development workflow unchanged

## v0.6.2

**Release Date**: July 6, 2026  
**Type**: Rebranding & Production Monitoring

Public highlights:

- **Project Rebranding**: Renamed to QueryMind（智询）
- **Monitoring Stack**: Prometheus + Grafana + Alertmanager
- **Enhanced Health Checks**: 6 dependency health check functions
- **Business Metrics**: Agent execution, retrieval quality, LLM costs, cache hits
- **Structured Logging**: JSON-formatted logs with Structlog
- **Circuit Breaker Integration**: LLM, vector store, graph store wrappers

Key metrics:
- Health check services: 3 → 8 (+167%)
- Alert rules: 0 → 30+
- Visualization panels: 0 → 14
- Monitoring docs: ~82 pages

## v0.6.1

**Release Date**: July 6, 2026  
**Type**: Architecture Enhancement & Docker Support

Public highlights:

- **Docker Containerization**: Production-ready Dockerfile, docker-compose orchestration
- **Agent Architecture**: Unified base classes, validation framework, result schemas
- **Admin Dashboard**: Agent quality monitoring, web activity tracking, system monitor
- **Security Enhancements**: SECURITY.md documentation, improved JWT handling
- **Web Research Agent**: Activity logging, data manager, alert system

Key metrics:
- One-command deployment: `docker-compose up -d`
- Health checks for all services
- Zero breaking changes

