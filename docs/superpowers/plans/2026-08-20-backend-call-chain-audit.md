# Backend Call-Chain Audit Implementation Plan

> **For agentic workers:** Execute this plan inline. Do not delegate work, inspect frontend code, add features, or refactor unrelated code.

**Goal:** Audit the complete backend call chains and minimally fix only reproducible functional, logical, security, data-integrity, concurrency, and stability defects.

**Architecture:** Start from FastAPI application assembly and registered routes, then trace each public/admin API through dependencies, services, orchestration/agents, repositories/databases/tools, and response mapping. Confirm every suspected defect against upstream and downstream callers, add a focused failing regression test, then apply the smallest API-compatible fix.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, asyncio, SQLite, LangGraph/LangChain, pytest.

**Spec:** This document records the backend-only requirements supplied in the 2026-08-20 user request.

## Global Constraints

- Inspect and modify backend code only; exclude `frontend/` completely.
- Do not add business features or perform broad refactors.
- Ignore naming, formatting, comments, and other style-only concerns.
- Preserve existing architecture and API compatibility.
- Treat the dirty worktree as user-owned and preserve unrelated edits.
- Report only evidence-backed P0/P1/P2 defects in the requested Chinese format.
- Every production fix requires a regression test that fails before the fix and passes after it.

---

### Task 1: Establish the backend baseline

**Files:**
- Inspect: `pyproject.toml`
- Inspect: `app/**/*.py`
- Inspect: `tests/**/*.py`

- [ ] Run `python -m compileall -q app` and record the exit code.
- [ ] Run the configured backend static checker when installed; record missing tooling as blocked.
- [ ] Run the existing backend suite with `pytest -q` and preserve the full failure summary.

### Task 2: Map API and dependency boundaries

**Files:**
- Inspect: `app/api/application/factory.py`
- Inspect: `app/api/application/router_registry.py`
- Inspect: `app/api/deps/**/*.py`
- Inspect: `app/api/routes/**/*.py`

- [ ] Enumerate registered routers and HTTP methods from the instantiated FastAPI application.
- [ ] Trace authentication, tenant, session, and admin dependencies into every stateful route family.
- [ ] Verify request validation, response schema, exception translation, and status-code contracts.

### Task 3: Trace query and agent execution

**Files:**
- Inspect: `app/api/query/**/*.py`
- Inspect: `app/orchestration/**/*.py`
- Inspect: `app/pipeline/**/*.py`
- Inspect: `app/agents/**/*.py`
- Inspect: `app/retrievers/**/*.py`
- Inspect: `app/tools/**/*.py`

- [ ] Trace standard and streaming query paths from route to final response.
- [ ] Check router/planner/RAG/tool/synthesizer execution, fallbacks, awaits, retries, duplicate execution, and state propagation.
- [ ] Verify degraded results cannot masquerade as successful business execution.

### Task 4: Trace persistence and authorization

**Files:**
- Inspect: `app/services/auth/**/*.py`
- Inspect: `app/services/sessions/**/*.py`
- Inspect: `app/services/documents/**/*.py`
- Inspect: `app/services/connectors/**/*.py`
- Inspect: `app/services/prompts/**/*.py`
- Inspect: `app/database/**/*.py`
- Inspect: `app/mcp/**/*.py`

- [ ] Trace create/read/update/delete operations through commit/row-count verification and response mapping.
- [ ] Verify user/tenant/session ownership is enforced at both route and storage boundaries.
- [ ] Check SQL construction, filesystem paths, outbound URLs, redirects, SSRF controls, secrets, and exception handling.

### Task 5: Reproduce and minimally repair confirmed defects

**Files:**
- Test: the closest matching file under `tests/`
- Modify: only the confirmed root-cause backend file under `app/`

- [ ] For each confirmed defect, write one behavior-focused regression test with hand-derived expectations.
- [ ] Run the exact test and verify it fails for the expected production behavior.
- [ ] Apply one minimal root-cause fix without unrelated cleanup.
- [ ] Run the exact test and its nearest related suite until green.

### Task 6: Verify and report

**Files:**
- Create: `.codex-audit/backend-2026-08-20/audit_report.md`
- Create: `.codex-audit/backend-2026-08-20/audit_report.json`

- [ ] Re-read every modified call chain from route through response.
- [ ] Run focused tests, then the complete available backend suite.
- [ ] Review `git diff -- app tests` and confirm no frontend or unrelated production edits.
- [ ] Produce matching Markdown and JSON reports with `发现问题`, `可新增功能`, `实施计划`, and `执行摘要`; state that feature additions are intentionally out of scope.
