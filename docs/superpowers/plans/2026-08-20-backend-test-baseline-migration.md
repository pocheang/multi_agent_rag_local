# Backend Test Baseline Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 47 backend pytest collection failures caused by retired Agent/Graph imports and missing declared dependencies, then restore a complete backend suite gate without reintroducing retired architecture or changing frontend code.

**Architecture:** Tests that still describe supported behavior move to the current `app.agents.*` packages, `RAGPipeline`, `OrchestrationEngine`, knowledge-graph clients, or current services. Tests that only exercise removed LangGraph nodes/workflows are deleted only after their behavior is mapped to current contract tests. Environment failures are fixed through declared dependency extras and the project environment, never through global skips or collection exclusions.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, FastAPI, SQLAlchemy, LangGraph, MCP SDK, pandas/PyMuPDF/pdfplumber, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-20-backend-test-baseline-migration-design.md`

## Global Constraints

- Work only in backend Python code, backend tests, dependency metadata, and backend audit documentation. Do not inspect or modify `frontend/`.
- Preserve API and production behavior. Do not restore compatibility wrappers removed by `d1075732`, `54192131`, `5d05e6f5`, `e322be7e`, or `ccbaec34`.
- Do not add `pytest` collection exclusions, global skips, or broad markers to conceal failures.
- Before editing each path, run `git status --short -- <path>` and `git diff -- <path>`. Several relevant paths are already dirty; preserve every pre-existing hunk.
- Do not stage a dirty file wholesale. For pre-existing dirty paths, leave the combined file unstaged unless a task-only patch can be staged and verified independently. Every commit must be checked with `git diff --cached --check` and `git diff --cached --name-only`.
- A production-code fix is allowed only when a current public entry point is genuinely broken and a failing regression test demonstrates it. Keep the fix minimal.
- Use `.venv\Scripts\python.exe` for all Python, pip, pytest, and compile commands so collection and execution use one environment.
- After each task, run its focused tests and `python -m pytest --collect-only -q`; do not continue while that task introduces a new collection error.

---

## Task 1: Freeze the 47-file baseline and dependency evidence

**Files:**

- Create: `docs/development/backend-test-baseline-migration.md`
- Inspect: `pyproject.toml`
- Inspect: `tests/agents/test_answer_validator.py`
- Inspect: `tests/agents/test_answer_validator_cascade.py`
- Inspect: `tests/agents/test_context_tracker.py`
- Inspect: `tests/agents/test_fact_verification.py`
- Inspect: `tests/agents/test_hallucination_detection.py`
- Inspect: `tests/agents/test_quality_orchestrator.py`
- Inspect: `tests/agents/test_react_agent_tools.py`
- Inspect: `tests/agents/test_relevance_scoring.py`
- Inspect: `tests/agents/test_retrieval_quality.py`
- Inspect: `tests/agents/test_route_accuracy.py`
- Inspect: `tests/agents/test_route_validator.py`
- Inspect: `tests/agents/test_router_accuracy.py`
- Inspect: `tests/agents/test_router_calibration.py`
- Inspect: `tests/agents/test_router_calibration_integration.py`
- Inspect: `tests/agents/test_router_enhanced.py`
- Inspect: `tests/agents/test_router_fallback.py`
- Inspect: `tests/agents/test_synthesis_citation.py`
- Inspect: `tests/graph/test_critical_fixes.py`
- Inspect: `tests/graph/test_cypher_validation.py`
- Inspect: `tests/graph/test_graph_rag_validation.py`
- Inspect: `tests/integration/test_batch_chart_extraction.py`
- Inspect: `tests/integration/test_session_language_tracking.py`
- Inspect: `tests/integration/test_streaming_pdf.py`
- Inspect: `tests/mcp/test_server_contracts.py`
- Inspect: `tests/mcp/test_server_transport.py`
- Inspect: `tests/performance/test_batch_benchmarks.py`
- Inspect: `tests/performance/test_benchmarks.py`
- Inspect: `tests/retrievers/test_query_expansion_integration.py`
- Inspect: `tests/services/multimodal/test_image_processor.py`
- Inspect: `tests/services/multimodal/test_table_extractor.py`
- Inspect: `tests/test_agent_resilience.py`
- Inspect: `tests/test_agent_scope_filtering.py`
- Inspect: `tests/test_batch_chart_extractor.py`
- Inspect: `tests/test_graph_rag_agent_enhanced.py`
- Inspect: `tests/test_graph_rag_optimization.py`
- Inspect: `tests/test_neo4j_delete_by_source.py`
- Inspect: `tests/test_react_agent.py`
- Inspect: `tests/test_streaming_analytics_logging.py`
- Inspect: `tests/test_streaming_react_agent_class.py`
- Inspect: `tests/test_weight_optimization.py`
- Inspect: `tests/test_workflow_fixes.py`
- Inspect: `tests/unit/test_chinese_document_indexer.py`
- Inspect: `tests/unit/test_chinese_query_preprocessor.py`
- Inspect: `tests/unit/test_chinese_tokenizer.py`
- Inspect: `tests/unit/test_synthesis_language.py`
- Inspect: `tests/unit/test_unified_agents.py`
- Inspect: `tests/unit/test_web_research_agent.py`

- [ ] Run the current collection gate and capture the exact failing file/module pairs:

  ```powershell
  .venv\Scripts\python.exe -m pytest --collect-only -q
  ```

  Expected: 47 collection errors matching the approved baseline; if the count differs, record the new count and reconcile every added or removed item before editing.

- [ ] Verify dependency state against package metadata:

  ```powershell
  .venv\Scripts\python.exe -c "import importlib.util as u; print({n: bool(u.find_spec(n)) for n in ('mcp','jieba','psutil','pandas')})"
  .venv\Scripts\python.exe -m pip check
  ```

  Expected before repair: `mcp`, `jieba`, and `psutil` are declared in `pyproject.toml` but absent from the environment; record the actual `pandas` state separately.

- [ ] In `docs/development/backend-test-baseline-migration.md`, create a 47-row matrix with columns `test file`, `missing import/dependency`, `retirement evidence`, `current owner`, `action`, and `focused verification`. Populate every row; allowed actions are only `migrate`, `delete-retired-contract`, `repair-test-import`, or `install-dependency`.

- [ ] Record the no-wrapper invariant:

  ```powershell
  rg -n "app\.(agents|graph)\.(answer_validator_agent|router_agent|vector_rag_agent|graph_rag_agent|react_agent|synthesis_agent|workflow|state|nodes)" app --glob "*.py"
  ```

  Expected: no active production call chain depends on a removed module. Historical strings in explicit shadow/compatibility assertions must be documented rather than rewritten blindly.

- [ ] Commit only the new migration matrix:

  ```powershell
  git add -- docs/development/backend-test-baseline-migration.md
  git diff --cached --check
  git commit -m "test: inventory retired backend test imports"
  ```

---

## Task 2: Restore the declared test environment and declare multimodal dependencies

**Files:**

- Modify: `pyproject.toml`
- Test: `tests/mcp/test_server_contracts.py`
- Test: `tests/mcp/test_server_transport.py`
- Test: `tests/unit/test_chinese_document_indexer.py`
- Test: `tests/unit/test_chinese_query_preprocessor.py`
- Test: `tests/unit/test_chinese_tokenizer.py`
- Test: `tests/integration/test_streaming_pdf.py`
- Test: `tests/services/multimodal/test_image_processor.py`
- Test: `tests/services/multimodal/test_table_extractor.py`

- [ ] Confirm the focused tests fail only because their declared imports are absent:

  ```powershell
  .venv\Scripts\python.exe -m pytest -q tests/mcp/test_server_contracts.py tests/mcp/test_server_transport.py tests/unit/test_chinese_document_indexer.py tests/unit/test_chinese_query_preprocessor.py tests/unit/test_chinese_tokenizer.py tests/integration/test_streaming_pdf.py tests/services/multimodal/test_image_processor.py tests/services/multimodal/test_table_extractor.py
  ```

  Expected: collection failures name `mcp`, `jieba`, `psutil`, or the `pandas` import pulled in by `app.services.multimodal`.

- [ ] In `[project.optional-dependencies]`, add a `multimodal` extra containing the production imports used by `app/services/multimodal/table_extractor.py`: `pandas>=2.2.0,<3.0`, `PyMuPDF>=1.24.0`, `pdfplumber>=0.11.0`, and `tabulate>=0.9.0`. Add `multimodal` to the `full` meta-extra. Do not move these packages into core dependencies.

- [ ] Install the project’s declared backend test environment:

  ```powershell
  .venv\Scripts\python.exe -m pip install -e ".[dev,multimodal]"
  ```

  Expected: installation includes the already-declared core packages `mcp`, `jieba`, and `psutil`, plus the new multimodal extra.

- [ ] Verify dependency imports and metadata consistency:

  ```powershell
  .venv\Scripts\python.exe -c "import jieba, mcp, pandas, psutil, fitz, pdfplumber, tabulate; print('dependency imports ok')"
  .venv\Scripts\python.exe -m pip check
  ```

  Expected: `dependency imports ok` and `No broken requirements found.`

- [ ] Rerun the eight focused files. Any failure after successful imports is a separate contract failure and must be diagnosed before changing expectations.

- [ ] Commit only `pyproject.toml` if its task-specific dependency hunk can be separated from pre-existing user changes; otherwise leave it unstaged and record that fact in the migration matrix:

  ```powershell
  git diff -- pyproject.toml
  git diff --cached --check
  git commit -m "build: declare multimodal backend test dependencies"
  ```

---

## Task 3: Migrate validation, routing, and configuration tests to canonical Agent modules

**Files:**

- Modify: `tests/agents/test_answer_validator.py`
- Modify: `tests/agents/test_answer_validator_cascade.py`
- Modify: `tests/agents/test_context_tracker.py`
- Modify: `tests/agents/test_fact_verification.py`
- Modify: `tests/agents/test_hallucination_detection.py`
- Modify: `tests/agents/test_quality_orchestrator.py`
- Modify: `tests/agents/test_relevance_scoring.py`
- Modify: `tests/agents/test_retrieval_quality.py`
- Modify: `tests/agents/test_route_accuracy.py`
- Modify: `tests/agents/test_route_validator.py`
- Modify: `tests/agents/test_router_accuracy.py`
- Modify: `tests/agents/test_router_calibration.py`
- Modify: `tests/agents/test_router_calibration_integration.py`
- Modify: `tests/agents/test_router_enhanced.py`
- Modify: `tests/agents/test_router_fallback.py`
- Modify: `tests/agents/test_synthesis_citation.py`
- Modify: `tests/unit/test_synthesis_language.py`
- Modify: `tests/unit/test_unified_agents.py`

- [ ] Run these 18 files and retain the failing collection output as the red baseline.

- [ ] Replace removed validation paths with their exact current owners:

  - `answer_validator_agent` -> `app.agents.validation.public` and, only for NLI helpers, `app.agents.validation.nli`.
  - `validation_cascade` -> `app.agents.validation.cascade`.
  - `fact_verification` -> `app.agents.validation.fact_verification`.
  - `hallucination_patterns` -> `app.agents.validation.hallucination_patterns`.
  - `quality_orchestrator_agent` -> `app.agents.validation.quality_orchestrator`.

- [ ] Replace removed router/config paths with their exact current owners:

  - `router_agent` -> `app.agents.router.routing`; import `LegacyRouteDecision` under the local name `RouteDecision` only where the old test data shape requires it.
  - `route_validator_agent` -> `app.agents.router.validator`.
  - `route_accuracy_tracker` -> `app.agents.router.accuracy`.
  - `router_calibration` -> `app.agents.router.calibration`.
  - `router_examples` -> `app.agents.router.examples`.
  - `agent_config` and `unified_config` -> `app.agents.shared.config`.

- [ ] Update every `patch(...)`, logger name, and dynamic import string in these files to the module where the looked-up symbol is actually resolved. Do not patch the retired path and do not add proxy modules.

- [ ] Move remaining supported imports as follows: `relevance_scoring` -> `app.agents.rag.relevance`, `retrieval_quality_agent` -> `app.agents.rag.retrieval_quality`, `synthesis_agent` -> `app.agents.synthesizer.generation`, `synthesis_templates` -> `app.agents.synthesizer.templates`, `base_agent` -> `app.agents.shared.base`, and `shared_utils` -> `app.agents.shared.utils`.

- [ ] Migrate `tests/agents/test_context_tracker.py` from the retired Agent wrapper to `app.services.sessions.context_tracker`; preserve only current session-history and isolation contracts, and patch the service's real lookup sites.

- [ ] Run the 18 focused files. Expected: collection succeeds and assertions exercise the current modules. If a current symbol has a different public contract, update the fixture/assertion to the current contract only after tracing its production caller.

- [ ] Run stale-import and collection gates:

  ```powershell
  rg -n "app\.agents\.(answer_validator_agent|validation_cascade|fact_verification|hallucination_patterns|quality_orchestrator_agent|relevance_scoring|retrieval_quality_agent|route_accuracy_tracker|route_validator_agent|router_agent|router_calibration|router_examples|agent_config|unified_config|synthesis_agent|synthesis_templates|base_agent|shared_utils)" tests --glob "*.py"
  .venv\Scripts\python.exe -m pytest --collect-only -q
  ```

  Expected: no unclassified stale import remains. Explicit historical-string tests must be listed in the matrix.

- [ ] Stage only task-owned hunks and commit:

  ```powershell
  git diff --cached --check
  git commit -m "test: migrate agent contract imports"
  ```

---

## Task 4: Migrate RAG, ReAct, scope, resilience, and web tests

**Files:**

- Modify: `tests/agents/test_react_agent_tools.py`
- Modify: `tests/test_react_agent.py`
- Modify: `tests/test_agent_scope_filtering.py`
- Modify: `tests/test_agent_resilience.py`
- Modify: `tests/retrievers/test_query_expansion_integration.py`
- Modify: `tests/unit/test_web_research_agent.py`
- Modify: `tests/test_weight_optimization.py`

- [ ] Run the seven focused files and capture their initial collection/runtime failures.

- [ ] Apply the supported module mappings:

  - `react_agent` -> `app.agents.tool.react`.
  - `vector_rag_agent` -> `app.agents.rag.vector`.
  - `graph_rag_agent` -> `app.agents.rag.graph`.
  - `web_research_agent` -> `app.agents.rag.web`.
  - `web_research_utils` -> `app.agents.rag.web_utils`.
  - `graph_rag_agent_enhanced` -> `app.agents.rag.enhanced_graph`.
  - `graph_rag_cache` -> `app.agents.rag.cache`.

- [ ] In `tests/test_agent_scope_filtering.py`, import `app.agents.rag.graph` and `app.agents.rag.vector` as module aliases so monkeypatches target the canonical module objects.

- [ ] In `tests/test_agent_resilience.py`, remove fake `sys.modules` entries for retired paths. Patch canonical dependencies at their lookup sites; retain only resilience assertions reachable from current RAG/Router/Tool services. Delete an individual test function if its sole subject is a retired compatibility import mechanism, and document that function in the migration matrix.

- [ ] For query expansion and weight optimization tests, trace the current retriever/optimizer owner before editing imports; keep assertions about ranking, weight normalization, and fallback behavior, but remove assertions about retired wrapper construction.

- [ ] Run the seven focused files, then:

  ```powershell
  rg -n "app\.agents\.(react_agent|vector_rag_agent|graph_rag_agent|web_research_agent|web_research_utils|graph_rag_agent_enhanced|graph_rag_cache)" tests --glob "*.py"
  .venv\Scripts\python.exe -m pytest --collect-only -q
  ```

  Expected: no active import or patch target points to a removed RAG/Tool module.

- [ ] Stage only task-owned hunks and commit:

  ```powershell
  git diff --cached --check
  git commit -m "test: migrate rag and tool test contracts"
  ```

---

## Task 5: Migrate knowledge-graph tests and remove only retired workflow contracts

**Files:**

- Modify: `tests/graph/test_critical_fixes.py`
- Modify: `tests/graph/test_cypher_validation.py`
- Modify: `tests/graph/test_graph_rag_validation.py`
- Modify: `tests/test_graph_rag_agent_enhanced.py`
- Modify: `tests/test_graph_rag_optimization.py`
- Modify: `tests/test_neo4j_delete_by_source.py`
- Modify or delete after coverage mapping: `tests/integration/test_session_language_tracking.py`
- Delete after coverage mapping: `tests/test_streaming_analytics_logging.py`
- Delete after coverage mapping: `tests/test_streaming_react_agent_class.py`
- Delete after coverage mapping: `tests/test_workflow_fixes.py`
- Modify: `tests/integration/test_multilingual_workflow.py`
- Modify: `tests/security/test_multi_tenant_isolation.py`
- Verify: `tests/pipeline/test_rag_pipeline_streaming.py`
- Verify: `tests/pipeline/test_rag_pipeline_orchestration.py`
- Verify: `tests/orchestration/test_engine.py`
- Verify: `tests/api/test_query_execution_id.py`
- Verify: `tests/api/test_query_stream_ownership.py`
- Verify: `tests/api/test_analytics.py`

- [ ] Run the 12 affected files plus the six current replacement suites. Capture both collection errors and runtime-only stale imports.

- [ ] Migrate supported graph imports: `app.graph.neo4j_client` -> `app.graph.knowledge.client`, `app.graph.cypher_validation` -> `app.graph.knowledge.cypher_validation`, `app.agents.graph_rag_agent` -> `app.agents.rag.graph`, and enhanced/cache imports to `app.agents.rag.enhanced_graph` / `app.agents.rag.cache`. Update patch targets at lookup sites.

- [ ] Map each retired workflow test to current coverage in the migration matrix before deletion:

  - old stream sequencing and done/error events -> `tests/pipeline/test_rag_pipeline_streaming.py` and `tests/api/test_query_execution_id.py`;
  - old ReAct streaming class behavior -> `tests/pipeline/test_rag_pipeline_orchestration.py` and `tests/orchestration/test_engine.py`;
  - old streaming analytics writes -> `tests/api/test_analytics.py` and current execution-event tests;
  - old workflow fixes -> `tests/api/test_query_stream_ownership.py`, `tests/pipeline/test_rag_pipeline_orchestration.py`, and engine contract tests.

- [ ] For `tests/integration/test_session_language_tracking.py`, preserve session-isolation assertions by moving them to direct `app.services.session_language` tests or the current request/pipeline boundary. Delete only synthesis-node-specific tests after verifying equivalent multilingual/session coverage.

- [ ] Remove runtime imports of `app.graph.workflow`, `app.graph.state`, `app.graph.nodes.*`, and removed stream processor/safe-wrapper modules from `tests/integration/test_multilingual_workflow.py` and `tests/security/test_multi_tenant_isolation.py`. Rewrite those cases against `RAGPipeline` or the API dependency seam used in production; do not recreate graph modules.

- [ ] Run all Task 5 affected and replacement suites, then enforce:

  ```powershell
  rg -n "app\.graph\.(workflow|state|nodes|neo4j_client|cypher_validation|streaming\.(stream_processor|safe_wrappers))" tests --glob "*.py"
  .venv\Scripts\python.exe -m pytest --collect-only -q
  ```

  Expected: only explicitly documented historical-string assertions remain, and collection has no Graph/workflow errors.

- [ ] Stage only mapped migrations/deletions and commit:

  ```powershell
  git diff --cached --check
  git commit -m "test: retire obsolete graph workflow contracts"
  ```

---

## Task 6: Repair benchmark and chart-extraction import infrastructure

**Files:**

- Modify: `tests/performance/test_benchmarks.py`
- Modify: `tests/performance/test_batch_benchmarks.py`
- Modify: `app/ingestion/extraction/charts_batch.py`
- Test: `tests/integration/test_batch_chart_extraction.py`
- Test: `tests/test_batch_chart_extractor.py`
- Test: `tests/unit/test_chart_extractor.py`
- Test: `tests/test_external_vision_redaction.py`

- [ ] Run the six focused files. Expected red failures include top-level `benchmark_pdf_processing` and `.chart_extractor` imports.

- [ ] Change both performance tests to import `tests.performance.benchmark_pdf_processing`; `tests/performance/__init__.py` already makes the package explicit.

- [ ] Add or retain a focused test that imports `app.ingestion.extraction.charts_batch` and patches the symbol at `app.ingestion.extraction.charts_batch.extract_chart_data_with_vision`.

- [ ] Make the minimal production fix in `app/ingestion/extraction/charts_batch.py`: replace `from .chart_extractor import extract_chart_data_with_vision` with `from .charts import extract_chart_data_with_vision`. Do not alter batch behavior, concurrency, result ordering, or exception conversion.

- [ ] If tests still reference `app.ingestion.utils.batch_chart_extractor` / `app.ingestion.utils.chart_extractor`, first verify whether those are active compatibility paths. Migrate to `app.ingestion.extraction.charts_batch` / `app.ingestion.extraction.charts` when production no longer uses the utils path; do not add another wrapper.

- [ ] Run the six focused files and collection gate. Expected: imports succeed, batch ordering and exception-as-error-dict behavior remain unchanged.

- [ ] Stage only task-owned hunks and commit:

  ```powershell
  git diff --cached --check
  git commit -m "fix: repair backend test module imports"
  ```

---

## Task 7: Reach zero collection errors and resolve runtime failures by root cause

**Files:**

- Modify: only backend tests identified by the complete run
- Modify: production backend files only when a new failing regression proves a current-contract defect
- Update: `docs/development/backend-test-baseline-migration.md`

- [ ] Run collection until it reaches zero errors:

  ```powershell
  .venv\Scripts\python.exe -m pytest --collect-only -q
  ```

  For every residual error, add a matrix row or update an existing row before editing. Do not solve collection by excluding a directory.

- [ ] Run the complete suite with failure limit disabled:

  ```powershell
  .venv\Scripts\python.exe -m pytest -q
  ```

- [ ] Classify each runtime failure as one of:

  - stale test contract: migrate fixture, patch target, or expected current schema;
  - unavailable external system: use the repository’s existing fixture/mock boundary or an already-defined integration marker;
  - current production defect: write the smallest failing regression at the current public boundary, make the minimal fix, and rerun its API -> service -> agent/tool -> repository/response chain.

- [ ] Specifically search for runtime-only retired imports that collection cannot see:

  ```powershell
  rg -n "app\.(agents|graph)\.(answer_validator_agent|router_agent|vector_rag_agent|graph_rag_agent|react_agent|synthesis_agent|web_research_agent|workflow|state|nodes|streaming\.stream_processor|streaming\.safe_wrappers)" tests --glob "*.py"
  ```

  Expected: zero executable references; documented literal strings in tests of shadow blocking are the sole permitted exception.

- [ ] Rerun each corrected failure group, then rerun the complete suite. Record passed/failed/skipped counts and elapsed time in the migration document.

- [ ] Stage only independently verified task changes and commit:

  ```powershell
  git diff --cached --check
  git commit -m "test: restore complete backend suite execution"
  ```

---

## Task 8: Re-run the existing backend regression gate and publish evidence

**Files:**

- Update: `docs/development/backend-test-baseline-migration.md`
- Update: `.codex-audit/backend-2026-08-20/README.md` or the existing backend audit summary file that already records the 155-test gate

- [ ] Run syntax and import checks:

  ```powershell
  .venv\Scripts\python.exe -m compileall -q app tests
  .venv\Scripts\python.exe -c "from app.api.application.factory import create_app; app=create_app(); print(len(app.routes))"
  ```

  Expected: compile succeeds and the application still registers 169 routes unless an independently documented pre-existing workspace change has altered the count.

- [ ] Run execution-blocking Ruff rules:

  ```powershell
  .venv\Scripts\python.exe -m ruff check app tests --select E9,F63,F7,F82
  ```

  Expected: no execution-blocking lint errors.

- [ ] Rerun the audit's named security/call-chain evidence set:

  ```powershell
  .venv\Scripts\python.exe -m pytest -q tests/api/test_admin_route_security.py tests/api/test_evaluation_path_security.py tests/api/test_query_backend_call_chain.py tests/api/test_query_cache_context.py tests/api/test_readiness_response_security.py tests/api/test_session_management_security.py tests/services/test_model_base_url_security.py tests/services/test_web_activity_data_manager_failures.py
  ```

  Expected: every named regression passes. The final complete-suite command is the authoritative superset of the earlier 155-test aggregate, whose original path list was not preserved in the audit report.

- [ ] Run final environment and suite gates:

  ```powershell
  .venv\Scripts\python.exe -m pip check
  .venv\Scripts\python.exe -m pytest --collect-only -q
  .venv\Scripts\python.exe -m pytest -q
  ```

  Expected: dependency consistency, zero collection errors, and complete suite execution without unclassified failures.

- [ ] Verify scope and compatibility constraints:

  ```powershell
  git diff --name-only -- frontend
  git diff --check
  rg -n "norecursedirs|collect_ignore|pytest_collection_modifyitems" pyproject.toml tests --glob "*.py" --glob "*.toml" --glob "*.ini"
  ```

  Expected: no task-created frontend diff and no new collection-hiding mechanism.

- [ ] Update both evidence documents with the final 47-row disposition, deleted-test coverage mappings, dependency versions, commands, counts, and any genuinely external prerequisite that could not be supplied locally.

- [ ] Commit only the evidence files:

  ```powershell
  git add -- docs/development/backend-test-baseline-migration.md .codex-audit/backend-2026-08-20
  git diff --cached --check
  git commit -m "docs: record restored backend suite gate"
  ```
