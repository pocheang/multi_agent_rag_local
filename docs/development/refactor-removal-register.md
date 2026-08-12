# Refactor removal register

## Typed orchestration cleanup (2026-08-11)

The typed cutover removed the last production callers of the compatibility
workflow executor. A fresh import and symbol audit across `app`, `scripts`,
and `tests` found only self-references for both paths below; a dynamic-import
audit also found no string-based reference. The files were deleted after
explicit authorization.

| Deleted path | Replacement or retirement rationale | Import-audit evidence |
| --- | --- | --- |
| `app/orchestration/compatibility_executor.py` | Retired second workflow owner. Public execution is `RAGPipeline` to typed `OrchestrationEngine` and canonical capabilities. | No external import or `LegacyWorkflowCompatibilityExecutor`/`CORE_CAPABILITY_CATALOG` reference in `app`, `scripts`, or `tests`. |
| `app/orchestration/compatibility_capabilities.py` | Retired assembly graph that existed only to feed the deleted executor. | No external import or dynamic reference in `app`, `scripts`, or `tests`. |
| `app/pipeline/post_execution.py` | Retired pipeline-level re-export; source-scope post-processing is directly owned by `app.orchestration.compatibility_post_execution`. | No external import in `app`, `scripts`, or `tests`; only this historical register mentioned the path. |
| `app/agents/rag/compatibility.py` | Retired retrieval adapter superseded by typed `RAGAgentService`. | No external import in `app`, `scripts`, `tests`, or `docs`. |
| `app/agents/tool/compatibility.py` | Retired reasoning adapter superseded by typed `ToolAgentService`. | No external import in `app`, `scripts`, `tests`, or `docs`. |
| `app/agents/synthesizer/compatibility.py` | Retired answer adapter superseded by typed `SynthesizerAgentService`. | No external import in `app`, `scripts`, `tests`, or `docs`. |
| `app/agents/legacy/__init__.py` | Empty historical package entrypoint with no exported implementation. | No external import in `app`, `scripts`, or `tests`. |

## Classification governance

`config/refactor_cleanup_allowlist.json` keeps inventory exemptions separate
from module stewardship. A classification records an owner, replacement, and
removal condition; it is never permission to delete without a fresh runtime
import audit.

| Classification | Meaning |
| --- | --- |
| `capability` | Supported user-facing or operational capability. |
| `shared` | Cross-capability contract, configuration, model, cache, or package boundary. |
| `compatibility` | Explicit root re-export to one canonical module; it owns no implementation. |
| `legacy_adapter` | Compatibility re-export or request/result adapter with no second business implementation. |
| `historical_debt` | Retained older responsibility with a known limitation or pending caller migration. |
| `delete_candidate` | Potential removal target requiring an import audit and explicit removal work. |

## Final audited deletions (2026-08-09)

Before deletion, the following audit was run over production backend code and
permitted legacy scripts:

```text
rg -n --glob '*.py' "(app\.agents\.(answer_validator_batch|quality_logging|quality_thread_safety|report_agent)|from app\.agents\.(answer_validator_batch|quality_logging|quality_thread_safety|report_agent)|app\.api\.(auth|reports)|from app\.api\.(auth|reports)|import app\.api\.(auth|reports)|app\.services\.(optimized_rag_pipeline|adaptive_strategy)|from app\.services\.(optimized_rag_pipeline|adaptive_strategy)|import app\.services\.(optimized_rag_pipeline|adaptive_strategy))" app scripts
```

Result: no runtime import match for any of the eight deleted paths below. The audit
was repeated after deletion with the same result. No deletion was based only
on a filename or package move.

| Deleted path | Replacement or retirement rationale | Import-audit evidence |
| --- | --- | --- |
| `app/agents/answer_validator_batch.py` | Public validation enters `app.agents.answer_validator_agent.validate_answer`, which adapts to `app.agents.validation.cascade.ValidationCascade`. | No `app` or `scripts` import match. |
| `app/agents/quality_logging.py` | Retired historical dead code; no runtime replacement was needed. | Only self-references existed before deletion; no external `app`/`scripts` importer. |
| `app/agents/quality_thread_safety.py` | Retired historical dead code; no runtime replacement was needed. | Only self-references existed before deletion; no external `app`/`scripts` importer. |
| `app/api/auth.py.deprecated` | Retired deprecated path; active authentication is owned by `app.api.routes.auth`, dependencies, and auth helpers. | No `app` or `scripts` import match; historic `app.api.auth` text was not an import. |
| `app/api/reports.py` | Retired historical dead module; no runtime replacement was needed. | No `app` or `scripts` import match; unrelated `REPORTS` text in a script was not an import. |
| `app/services/optimized_rag_pipeline.py` | Retired unused second RAG workflow implementation. The supported public execution path is `app.pipeline.rag_pipeline.RAGPipeline`, which delegates retained execution through `app.orchestration.engine.OrchestrationEngine`; services do not own workflow sequencing. | Before deletion: `rg -n --glob '*.py' '(from\s+app\.services\.optimized_rag_pipeline\s+import|import\s+app\.services\.optimized_rag_pipeline|app\.services\.optimized_rag_pipeline|optimized_rag_pipeline|OptimizedRAGPipeline|get_optimized_pipeline|optimized_query)' app scripts`. The only matches were the target module's own definitions and self-references; no external `app` or `scripts` runtime importer was found. |
| `app/agents/report_agent.py` | Retired report-generation implementation with no live app, script, test, or operations/development documentation import. | The pre/post `app` and `scripts` import audit was empty; `HEAD:app/api/reports.py` is a separately deleted baseline dependency noted below. |
| `app/services/adaptive_strategy.py` | Retired a complete duplicate adaptive retrieval-policy implementation: `AdaptiveStrategyRouter`, its global router, and its only complexity helper were all unused. | Fresh pre-delete `rg` over `app`, `scripts`, `tests`, and `docs` found only definitions inside the target file; the same audit after deletion found no match. |

## Canonical Agent support modules and retained compatibility

The following root paths are explicit compatibility re-exports to their exact
canonical symbols;
their `compatibility` classification in the allowlist is an inventory fact,
not deletion approval.

| Root compatibility path | Exact canonical implementation |
| --- | --- |
| `agent_config.py` | `app.agents.shared.config` |
| `base_agent.py` | `app.agents.shared.base` |
| `result_schemas.py` | `app.agents.shared.result_schemas` |
| `shared_utils.py` | `app.agents.shared.utils` |
| `quality_config.py` | `app.agents.shared.quality_config` |
| `quality_models.py` | `app.agents.shared.quality_models` |
| `shared_cache.py` | `app.agents.shared.cache` |
| `router_agent.py` | `app.agents.router.routing` |
| `router_config.py` | `app.agents.router.config` |
| `router_calibration.py` | `app.agents.router.calibration` |
| `router_examples.py` | `app.agents.router.examples` |
| `route_validator_agent.py` | `app.agents.router.validator` |
| `route_accuracy_tracker.py` | `app.agents.router.accuracy` |
| `vector_rag_agent_unified.py` | `app.agents.rag.vector` |
| `enhanced_vector_rag_agent.py` | `app.agents.rag.enhanced_vector` and `app.agents.rag.vector.run_vector_rag` |
| `graph_rag_agent.py` | `app.agents.rag.graph` |
| `graph_rag_agent_enhanced.py` | `app.agents.rag.enhanced_graph` |
| `graph_rag_cache.py` | `app.agents.rag.cache` |
| `graph_rag_config.py` | `app.agents.rag.config` |
| `relevance_scoring.py` | `app.agents.rag.relevance` |
| `retrieval_quality_agent.py` | `app.agents.rag.retrieval_quality` |
| `web_research_agent.py` | `app.agents.rag.web` |
| `web_research_utils.py` | `app.agents.rag.web_utils` |
| `react_agent.py` | `app.agents.tool.react` |
| `synthesis_agent.py` | `app.agents.synthesizer.generation` |
| `synthesis_templates.py` | `app.agents.synthesizer.templates` |
| `unified_config.py` | `app.agents.shared.unified_config` |
| `fact_verification.py` | `app.agents.validation.fact_verification` |
| `hallucination_patterns.py` | `app.agents.validation.hallucination_patterns` |
| `quality_orchestrator_agent.py` | `app.agents.validation.quality_orchestrator` |
| `validation_cascade.py` | `app.agents.validation.cascade` and `app.agents.validation.models` |

Root paths that perform an intentional request/result conversion rather than a
plain re-export are `enhanced_router_agent.py` and `vector_rag_agent.py`. They
delegate to `router.routing` and `rag.vector.run_vector_rag` respectively;
neither contains a second routing or retrieval engine.
`answer_validator_agent.py` is a logic-free module-object alias to
`app.agents.validation.public`, whose production validation entry delegates to
`ValidationCascade`; it contains no result conversion or validation algorithm.
`app.agents.legacy` was later deleted after its final empty package entrypoint
had no remaining consumers.

The current `app` plus `scripts` audit found direct root-path callers for
`agent_config`, `quality_config`, `quality_models`, `shared_cache`,
`router_agent`, `route_validator_agent`, `graph_rag_cache`, `graph_rag_config`,
`retrieval_quality_agent`, `quality_orchestrator_agent`, `react_agent`, and
`enhanced_vector_rag_agent`. Other retained re-exports have no direct local
caller in that audit, but remain public import compatibility paths; this
documentation-only correction makes no deletion decision for them.

`scripts/benchmark_optimization.py` imports `analyze_pdf_quality` and
`extract_document_entities` from `app.agents.graph_rag_cache`. Those two
symbols were already absent from `graph_rag_cache.py` before this refactor;
they remain a historical script debt, not a supported compatibility contract.
The script was not changed and no graph-cache API was added to mask that debt.

## Final boundary and review record

- `ValidationCascade` in `app.agents.validation.cascade` is the sole
  production validation engine. `validation_cascade.py` is a re-export and
  `answer_validator_agent.py` is a module-object alias to the canonical public
  validation entry. Claim-groundedness remains an internal cascade stage, not
  a second public validator.
- `app/api` is HTTP/SSE transport, dependency, and route-assembly code. A
  static import audit found no direct `app.api` route import of an Agent or
  legacy workflow.
- `RAGPipeline` translates public profiles and request/result contracts, then
  delegates retained workflow execution through `OrchestrationEngine`. The
  non-stream chain is `RAGPipeline → OrchestrationEngine.execute →
  LegacyWorkflowCompatibilityExecutor`; the stream chain is `RAGPipeline →
  OrchestrationEngine.execute_stream → LegacyWorkflowCompatibilityExecutor`.
  The compatibility executor owns legacy profile/workflow choice, explicit
  requested-tool invocation, stream execution, and terminal shaping. The
  implementation moved to
  `app.orchestration.compatibility_post_execution`; the retained
  `app.pipeline.post_execution` path is a re-export only for the existing API
  route imports, with no duplicate policy implementation.
- Before that move, this audit was run: `rg -n "post_execution" app scripts`.
  It found the pipeline implementation plus the established imports in
  `app.api.routes.query_request_execution` and
  `app.api.routes.query_stream{,_execution}`; no `scripts` import was found.
  Those route imports keep the narrow re-export in place. The canonical
  replacement is `app.orchestration.compatibility_post_execution`.
- Stream `answer_reset` keeps the historical `HEAD:app/api/routes/query.py`
  ordering: source-scope enforcement runs first, that scoped answer is saved,
  and a reset is emitted only when resynthesis changes it. Evidence-conflict
  warning decoration and other terminal metadata do not independently emit a
  reset.
- `app/mcp` owns protocol governance; `app/services` owns infrastructure,
  connectors, and narrow legacy service facades. Neither is a second workflow
  owner.
- Sol's first review found a router configuration-path regression after the
  move, eager package exports, and one canonical synthesis import that still
  used a legacy root. Terra restored the repository-root config paths, made
  router/rag/validation package public exports lazy, and changed the synthesis
  import to the canonical validation path. Sol's follow-up review was
  **ADDRESSED / PASS** with no new Critical or Important finding.
- Static evidence recorded for the scoped code: AST parsing of canonical
  modules, targeted Ruff `E9/F63/F7/F82`, targeted import-graph checks
  (including no cycles in the reviewed set), independent key-module imports,
  and `git diff --check`. These are static checks only; no test result is
  asserted here.

### 2026-08-09 final fact correction

- Later Sol reviews found that stream/non-stream delegation and the
  enhanced-vector compatibility root still needed correction. Terra moved all
  execution policy to `app.orchestration`, made both stream and non-stream
  paths pass through `OrchestrationEngine`, restored the historical
  `answer_reset` order, moved `EnhancedVectorRAGAgent` to
  `app.agents.rag.enhanced_vector`, and reduced its root path to an explicit
  re-export. The follow-up Sol reviews reported **ADDRESSED / PASS** for both
  review sets.
- All Agent support code covered by this work now has a canonical owner in
  `shared`, `router`, `rag`, `validation`, `services`, `orchestration`, or
  `workflow`. `agent_validator`, `context_tracker_agent`,
  `degradation_strategies`, `enhanced_rag_workflow`, and the
  `web_activity_*` paths are retained logic-free compatibility adapters;
  `report_agent` is deleted, not retained debt.
- Connector, Orchestration, and MCP packages; newly present route modules;
  and strict-quality, adaptive-routing, or model-selection behavior changes
  were already uncommitted work in the starting tree. They were preserved
  under the no-overwrite constraint. This refactor neither validates nor
  accepts those pre-existing feature changes as pure-refactor completion
  evidence.

## Task A shared-foundation compatibility correction (2026-08-09)

After `app.agents.rag.vector` moved its first-party imports to the canonical
shared modules, the prior `app`/`scripts` audit was empty:

```text
rg -n --glob '*.py' '(from\s+app\.agents\.(base_agent|unified_config)\s+import|import\s+app\.agents\.(base_agent|unified_config)(\s|$)|from\s+app\.agents\s+import\s+.*\b(base_agent|unified_config)\b)' app scripts
```

Result: no `app` or `scripts` runtime import match (ripgrep exit code 1).
That audit was insufficient to delete these public compatibility paths. The
following external/public compatibility audit found established imports:

```text
rg -n --glob '*.py' '(from\s+app\.agents\.(base_agent|unified_config)\s+import|import\s+app\.agents\.(base_agent|unified_config)\b|from\s+app\.agents\s+import\s+.*\b(base_agent|unified_config)\b)' tests docs/development docs/operations
```

Evidence includes `tests/unit/test_unified_agents.py` importing the historical
symbols and `docs/development/agent-code-organization.md` plus
`docs/operations/migration.md` documenting those imports. The root paths are
therefore retained as logic-free re-exports owned by `rag-platform`, with
their exact canonical replacements and retirement conditions in
`config/refactor_cleanup_allowlist.json`.

| Retained root compatibility path | Canonical replacement | Retirement condition |
| --- | --- | --- |
| `app/agents/base_agent.py` | `app.agents.shared.base` | The test and documented operations/development examples no longer import the historic path. |
| `app/agents/unified_config.py` | `app.agents.shared.unified_config` | The test and documented operations/development examples no longer import the historic path. |

## Task B context-tracker canonicalization (2026-08-09)

Before the move, the following production-code audit was run:

```text
rg -n --glob '*.py' '(from\s+app\.agents\.context_tracker_agent\s+import|import\s+app\.agents\.context_tracker_agent|from\s+app\.agents\s+import\s+.*\bcontext_tracker_agent\b)' app scripts
```

It found exactly three `app` callers and no `scripts` caller:

| Caller | Disposition |
| --- | --- |
| `app/pipeline/adapters.py` | Updated to import `app.services.context_tracker`. |
| `app/services/legacy_agent_runtime.py` | Updated to import `app.services.context_tracker`. |
| `app/workflow/enhanced_rag_workflow.py` | Migrated by Task C; it imports `app.services.context_tracker` directly. |

`app/agents/context_tracker_agent.py` is now a logic-free compatibility
re-export of `app.services.context_tracker`; the canonical service owns the
context store, TTL cleanup, periodic cleanup task, summary lifecycle, and all
context functions. Task C already migrated `enhanced_rag_workflow.py`; the
adapter may be deleted only after public tests and documented callers move off
the historic root path. The same owner, replacement, and condition are recorded in
`config/refactor_cleanup_allowlist.json`.

## Deliberately retained debt

- Root compatibility imports remain while production callers, scripts, or
  public result-shape callers still use them. Removing them would require a
  new `app`/`scripts` import audit and an explicit migration decision.
- The two benchmark imports described above predate this refactor and remain
  unresolved by design.
- The pre-existing parse typo in `app/ingestion/chunking/splitter.py` is
  corrected by Corrective Task J with the minimal legal quote literal needed
  for full-app static inspection; it does not change ingestion ownership or
  behavior.

No tests were run. The scoped refactor and this fact correction did not edit
tests, CI, frontend, dependencies, migrations, or deployment/release files.
Existing user changes in those areas were preserved. No commit, push, or PR
was made.

## Task C degradation and compatibility-workflow canonicalization (2026-08-09)

Before moving the implementations, the `app`/`scripts` import audit found the
strict-profile executor importing `app.agents.enhanced_rag_workflow` and the
workflow importing `app.agents.degradation_strategies`. The implementations
now live at `app.orchestration.degradation_strategies` and
`app.workflow.enhanced_rag_workflow`; the executor is the sole production
caller of the latter.

`tests/agents/test_enhanced_workflow.py`, `test_intelligent_retry.py`, and
`test_graceful_degradation.py` import and monkeypatch the historical workflow
module. `test_graceful_degradation.py` also imports the historical degradation
module. The two root modules are therefore retained as logic-free
`sys.modules` aliases to their canonical module objects rather than static
symbol re-exports, so existing monkeypatch targets affect the implementation
that executes. The root answer-validator path is retained with the same alias
form because the migrated workflow must not import a root legacy module.

The aliases are owned by `rag-platform`. Their retirement depends only on
remaining tests, documented/public compatibility consumers, and any actual
root-alias importer no longer using the historical path; the strict-profile
executor already imports the canonical workflow and is not a retirement
condition. Exact replacements and conditions are recorded in
`config/refactor_cleanup_allowlist.json`.
No production code imports the Task C root aliases. The workflow imports
canonical routing, retrieval, validation, shared-model, context-service, and
orchestration-degradation modules; its answer-reset and stream-terminal code
was moved unchanged.

## Task D Web Activity service canonicalization (2026-08-09)

Before moving the three implementations, this production-code audit was run:

```text
rg -n --glob '*.py' '(from\s+app\.agents\.(web_activity_alerts|web_activity_data_manager|web_activity_logger)\s+import|import\s+app\.agents\.(web_activity_alerts|web_activity_data_manager|web_activity_logger)(\s|$)|from\s+app\.agents\s+import\s+.*\b(web_activity_alerts|web_activity_data_manager|web_activity_logger)\b)' app scripts
```

It found two `app` callers and no `scripts` caller: `app.agents.rag.web`
used the logger and `app.services.legacy_web_activity` imported all three
modules lazily. Both first-party callers now import the canonical service
modules directly. The same audit was repeated after the move with no
`app` or `scripts` matches.

Read-only compatibility inspection found tests importing all three historic
paths, while `docs/operations/web-activity/deployment.md` and
`docs/operations/web-activity/logging.md` document the historic logger path.
The root modules therefore remain logic-free `sys.modules` aliases, preserving
module identity, public symbols, singleton state, file behavior, and existing
monkeypatch targets. Their canonical implementations are:

| Root compatibility path | Canonical implementation | Retirement condition |
| --- | --- | --- |
| `app/agents/web_activity_alerts.py` | `app.services.web_activity.alerts` | Tests and other concrete public compatibility consumers no longer import the historic path. |
| `app/agents/web_activity_data_manager.py` | `app.services.web_activity.data_manager` | Tests no longer import the historic path. |
| `app/agents/web_activity_logger.py` | `app.services.web_activity.logger` | Tests and operational documentation no longer import the historic path. |

## Task E audited deletion and Agent health service ownership (2026-08-09)

Before the Agent health move, the following production-code audit found only
`app/services/legacy_agent_health.py` importing the root validator (at its two
lazy lookup sites) and no `scripts` caller:

```text
rg -n --glob '*.py' '(from\s+app\.agents\.agent_validator\s+import|import\s+app\.agents\.agent_validator(\s|$)|from\s+app\.agents\s+import\s+.*\bagent_validator\b)' app scripts
```

The implementation now lives at `app.services.agent_health_validator`, and
`legacy_agent_health` imports that canonical service. Repeating the same
audit after the move returned no `app` or `scripts` matches (ripgrep exit code
1). The root `app/agents/agent_validator.py` is a no-business-logic
compatibility entry point that re-exports the validator and delegates its
documented command-line invocation to the canonical service.

Read-only public-compatibility inspection found no test import, but
`docs/operations/migration.md` documents
`python -m app.agents.agent_validator`. The root entry point is therefore
retained under `rag-platform`; its replacement and retirement condition are
recorded in `config/refactor_cleanup_allowlist.json`.

`report_agent.py` was deleted after this empty runtime-import audit:

```text
rg -n --glob '*.py' '(from\s+app\.agents\.report_agent\s+import|import\s+app\.agents\.report_agent(\s|$)|from\s+app\.agents\s+import\s+.*\breport_agent\b)' app scripts
```

The pre-delete result had no `app` or `scripts` match (ripgrep exit code 1),
and the same command after deletion remained empty. Read-only searches found
no test or operational/development documentation compatibility import. It had
no canonical replacement because no live caller used its report-generation
implementation. Its stale root classification was removed rather than being
allowlisted. Package initializers did not export either audited module, so no
stale package export remained to remove.

Baseline-dependency note: `HEAD:app/api/reports.py` imported and called the
historic `report_agent`, but `app/api/reports.py` was already deleted in the
starting dirty worktree and was not restored or modified by Task E. The
`report_agent` deletion remains valid only while that pre-existing reports
route deletion remains in effect; restoring the route requires restoring a
supported report capability or making a new explicit ownership decision.

## Corrective Task I: public contracts and dead adaptive strategy (2026-08-09)

The original runtime-only deletion audit for `result_schemas.py` and
`shared_utils.py` was not sufficient to remove their public import contracts.
A fresh compatibility audit found `tests/unit/test_unified_agents.py` and
`docs/operations/migration.md` importing the following historic symbols:

| Historical root path | Retained public symbols | Canonical owner |
| --- | --- | --- |
| `app.agents.result_schemas` | `AgentResult`, `RouterResult`, `VectorRAGResult`, `GraphRAGResult`, the remaining result models, type aliases, and conversion helpers | `app.agents.shared.result_schemas` |
| `app.agents.shared_utils` | `ContextFormatter`, `ResultValidator`, `CacheKeyGenerator`, `TextProcessor`, and the remaining utility classes | `app.agents.shared.utils` |

Both root paths are now logic-free re-exports and are recorded as
compatibility paths in the allowlist. Their canonical modules own the one
implementation; no independent root business implementation was restored.

Before deleting `app/services/adaptive_strategy.py`, the following fresh
audit was run across all required scopes:

```text
rg -n --glob '*.py' 'AdaptiveStrategyRouter|QueryComplexityAnalyzer|analyze_query_complexity|route_query_adaptive|get_complexity_analyzer|get_adaptive_router' app scripts tests
rg -n --glob '*.md' --glob '*.rst' 'AdaptiveStrategyRouter|QueryComplexityAnalyzer|analyze_query_complexity|route_query_adaptive|get_complexity_analyzer|get_adaptive_router' docs
```

It found only definitions inside the target module and no external caller or
documentation contract. The same targeted audit was repeated after deletion
with no match. `ComplexityLevel` is intentionally absent from this command:
`app.retrievers.parameter_tuning` defines an unrelated local type alias with
that generic name. The file was therefore removed as unused duplicate
adaptive retrieval policy; no complexity helper was retained because none had
a real caller.

## Corrective Task J: final evidence reconciliation (2026-08-09)

The current `git diff --name-status --diff-filter=D -- app` inventory contains
exactly eight paths, matching the deletion table above. `result_schemas.py`
and `shared_utils.py` are retained aliases, while `report_agent.py` and
`adaptive_strategy.py` are deleted. The initial forbidden-area manifest and
the full-app AST/Ruff outcomes are stored in the SDD evidence directory; tests
were not modified or run.

## Final backend convergence: removal evidence and owner boundary (2026-08-09)

This entry records the final-convergence removals. It is intentionally
append-only: earlier removal evidence, existing compatibility contracts, and
the starting dirty-worktree records remain authoritative for their respective
changes.

| Removed path | Pre-removal audit command and result | Canonical owner / replacement | Removal reason | Post-removal audit result |
| --- | --- | --- | --- | --- |
| `app/retrievers/fast_reranker.py` | `rg -n --glob '*.py' '(from\\s+app\\.retrievers\\.fast_reranker\\s+import|import\\s+app\\.retrievers\\.fast_reranker(\\s|$)|FastReranker)' app scripts` — only the target definition; no external `app` or `scripts` caller. | `app.retrievers.reranker` through the canonical hybrid retrieval chain. | Unused historical reranker implementation; retaining it would leave two apparent reranker owners. | Same command returned no match after deletion. |
| `app/retrievers/multi_path_retriever.py` | `rg -n --glob '*.py' '(from\\s+app\\.retrievers\\.multi_path_retriever\\s+import|import\\s+app\\.retrievers\\.multi_path_retriever(\\s|$)|MultiPathRetriever)' app scripts` — only the target definition; no external `app` or `scripts` caller. | `app.retrievers.hybrid_retriever` and its canonical vector/BM25/reranker composition. | Unused duplicate retrieval-strategy candidate with no production owner or compatibility caller. | Same command returned no match after deletion. |
| `app/prompts/query_decomposition.txt` | `rg -n --glob '*.py' 'query_decomposition\\.txt|query_decomposition' app scripts` — no runtime file read or external `app`/`scripts` caller of the text asset; the active decomposition prompt was migrated to the canonical prompt module. | `app.prompts.core.canonical_agent_prompts.QUERY_DECOMPOSITION_PROMPT`, consumed by `app.services.query_decomposer`. | Dead text asset duplicated the active prompt owner. | Same command returned no match for the removed asset after deletion; canonical Python prompt references remain. |
| `app/prompts/relevance_evaluation.txt` | `rg -n --glob '*.py' 'relevance_evaluation\\.txt|relevance_evaluation' app scripts` — no runtime file read or external `app`/`scripts` caller of the text asset. | `app.prompts` is the sole prompt owner; no live relevance-text prompt replacement is required because no production caller existed. | Unused historical prompt asset without a consumer or public compatibility contract. | Same command returned no match for the removed asset after deletion. |
| `app/prompts/quality_evaluation.txt` | `rg -n --glob '*.py' 'quality_evaluation\\.txt|quality_evaluation' app scripts` — no runtime file read or external `app`/`scripts` caller of the text asset. | `app.prompts` is the sole prompt owner; production quality evaluation remains owned by the canonical validation/orchestration capabilities. | Unused historical prompt asset without a consumer or public compatibility contract. | Same command returned no match for the removed asset after deletion. |

### Owner map and boundary-audit summary

The public query boundary remains singular:

```text
API -> RAGPipeline -> OrchestrationEngine -> canonical capability/workflow
```

`ValidationCascade` (`app.agents.validation.cascade`) is the only production
answer-validation engine. `app.prompts` is the only prompt owner, including
the canonical router, ReAct, synthesis/review, and query-decomposition
templates. `app.retrievers` is the only low-level retrieval-infrastructure
owner, with the live hybrid chain retaining `hybrid_retriever` and `reranker`.

The public CLI/benchmark scripts were moved from direct graph invocation to
`RAGPipeline`, while preserving their compatibility payload/metric handling.
The remaining old import paths are retained only as no-business-logic
compatibility exports where real documentation, test, or public invocation
contracts require them; they are not second implementations.

## Corrective Task K: API policy boundary and PDF helper removal (2026-08-09)

`app.api.utils.query_helpers.handle_pdf_agent_routing` was a historical API
utility that combined PDF routing, audit writes, and conversation-history
writes. The production PDF policy is already owned by
`app.orchestration.standard_request_policy`; retaining this unused helper
would preserve a second API-layer execution policy.

Before deletion, the required full-scope audit was run:

```text
rg -n "handle_pdf_agent_routing" app scripts tests docs config
```

The only match was the function definition in
`app/api/utils/query_helpers.py`; there were no production callers, test
imports, documentation contracts, configuration references, dynamic-import
references, or package exports. The same command was repeated after deletion
and returned no match (ripgrep exit code 1).

The following API compatibility symbols remain because `app.api.dependencies`
and the prompts route still use their existing names and signatures:

| API compatibility symbol | Canonical owner | Status |
| --- | --- | --- |
| `_normalize_agent_class_hint` | `app.orchestration.standard_request_policy.normalize_agent_class_hint` | Logic-free delegate retained. |
| `_resolve_effective_agent_class` | `app.orchestration.standard_request_policy.resolve_effective_agent_class` | Logic-free delegate retained. |
| `_normalize_retrieval_strategy` | `app.orchestration.standard_request_policy.normalize_retrieval_strategy` | Logic-free delegate retained. |
| `_effective_strategy_for_session` | `app.orchestration.standard_request_policy.effective_strategy_for_session` | Logic-free delegate retained. |

This move leaves orchestration independent of both `app.api` and
`app.pipeline`; it centralizes standard request classification and
session-profile selection without changing public API function signatures.

## Sol follow-up addressed (2026-08-09)

The Sol high read-only review reported `Critical = 0` and confirmed that the
public API path remains `API -> RAGPipeline -> OrchestrationEngine ->
canonical capability/workflow`. The follow-up items below were addressed
without changing public HTTP/SSE contracts, result payload fields, model
selection, retrieval semantics, or compatibility import signatures.

| Follow-up item | Canonical owner / compatibility decision | Evidence and behavior-preservation note |
| --- | --- | --- |
| API request classification and session retrieval policy | `app.orchestration.standard_request_policy` | `_normalize_agent_class_hint`, `_resolve_effective_agent_class`, `_normalize_retrieval_strategy`, and `_effective_strategy_for_session` remain at `app.api.utils.query_helpers` only as same-signature, logic-free delegates. Existing API callers keep their imports and behavior. |
| Uncalled PDF routing helper | Removed `app.api.utils.query_helpers.handle_pdf_agent_routing`; the live policy remains in `app.orchestration.standard_request_policy` | Before: `rg -n "handle_pdf_agent_routing" app scripts tests docs config` returned only the helper definition. After deletion, the identical command returned no match (ripgrep exit code 1). No public, test, documentation, config, dynamic-import, or package-export contract existed. |
| Compatibility executor result text | `app.orchestration.compatibility_executor` | Corrected the `user_file_inventory_only` `thoughts` encoding corruption. Field name, payload shape, event order, `answer_reset`, and `done.result` semantics are unchanged. |
| ReAct system prompt | `app.prompts.core.canonical_agent_prompts.REACT_SYSTEM_PROMPT` | `app.prompts.react_prompts.REACT_SYSTEM_PROMPT` is now a compatibility re-export; its user template and PromptManager surface remain available. The canonical prompt content is not duplicated. |
| Tool-agent factory | `app.agents.tool.factory` | `app.pipeline.tool_agent_factory` and `app.services.tool_agent_factory` are logic-free compatibility re-exports, and `app.api.runtime` imports the canonical factory directly. Existing import paths and factory behavior are preserved. |
| Obsolete retrieval configuration | No replacement required; active retrieval configuration remains under the canonical retriever stack | Before: `rg -n "fast_reranker|multi_path" app scripts config` found only unconsumed `fast_reranker_*` / `multi_path_*` settings and examples in `app.core.optimized_config`. After removal, the identical command returned no match. No runtime consumer existed. |
| Evaluation retrieval baseline | `app.evaluation.baselines.api_retriever` | `SimpleRetriever` and the direct retrieval calls moved out of the API route. `app.api.routes.evaluation` keeps request validation, error conversion, response fields, and the three strategy choices unchanged while delegating to the baseline owner. |

These follow-ups extend the original five audited removals; they are not
represented as a claim that the convergence changed only five files or five
items. Retained historical paths above are compatibility exports, not second
business implementations.

## Prompt directory migration and canonical ownership (2026-08-09)

This entry records the prompt-only directory migration. The initial
`git status --short` was captured before any work; the worktree already
contained unrelated backend, frontend, dependency, test, documentation, and
new-file changes. Those changes were preserved and are not attributed to this
migration.

The baseline evidence is a status snapshot rather than a content snapshot;
therefore, attribution for files that were already modified or untracked is
based on the recorded scope and the operations performed, not on a retroactive
hash comparison.

### Migration map

| Capability package | Implementation modules |
| --- | --- |
| `app.prompts.core` | `canonical_agent_prompts`, `router_prompts`, `intent_prompts`, `synthesis_prompts`, `review_prompts`, `react_prompts` |
| `app.prompts.retrieval` | `rag_quick_retrieval_prompts`, `self_rag_prompts` |
| `app.prompts.skills` | `ai_knowledge_prompts`, `cybersecurity_skills_prompts`, `comparison_timeline_prompts`, `pdf_web_prompts` |

`app.prompts.core.canonical_agent_prompts` is the sole runtime canonical owner
of `ROUTER_PROMPT_TEMPLATE`, `REACT_SYSTEM_PROMPT`, `ANSWER_PROMPT`,
`REVIEW_PROMPT`, and `QUERY_DECOMPOSITION_PROMPT`. The core ReAct module owns
only the established user template and imports the canonical ReAct system
prompt.

### Import and dynamic-loading audit

Before migration, the scoped audit was:

```text
rg -n --glob '*.py' --glob '*.md' --glob '*.json' 'app\.prompts|from \.((ai_knowledge|comparison_timeline|cybersecurity_skills|intent|manager|pdf_web|rag_quick_retrieval|react|review|router|self_rag|synthesis)_prompts)' app scripts tests docs config
rg -n --glob '*.py' 'import_module\([^)]*prompt|__import__\([^)]*prompt|find_spec\([^)]*prompt|spec_from_file_location\([^)]*prompt' app scripts tests
```

The results were package exports in `app.prompts.__init__` and
`app.prompts.manager`, the ReAct compatibility module, production imports from
`app.prompts`/the canonical module, and the backend prompt documentation. No
prompt module was loaded through a dynamic import or a configuration string.

After migration, the old absolute module-import audit was repeated:

```text
rg -n --glob '*.py' 'from app\.prompts\.(canonical_agent_prompts|router_prompts|intent_prompts|synthesis_prompts|review_prompts|react_prompts|rag_quick_retrieval_prompts|self_rag_prompts|ai_knowledge_prompts|cybersecurity_skills_prompts|comparison_timeline_prompts|pdf_web_prompts) import|import app\.prompts\.(canonical_agent_prompts|router_prompts|intent_prompts|synthesis_prompts|review_prompts|react_prompts|rag_quick_retrieval_prompts|self_rag_prompts|ai_knowledge_prompts|cybersecurity_skills_prompts|comparison_timeline_prompts|pdf_web_prompts)' app scripts tests
rg -n --glob '*.py' 'import_module\([^)]*prompt|__import__\([^)]*prompt|find_spec\([^)]*prompt|spec_from_file_location\([^)]*prompt' app scripts tests
```

The first audit has no remaining first-party caller of a flat root prompt
module; production code uses `app.prompts` or a capability path, and the
historical root modules remain import-only compatibility exports. The dynamic
prompt-loading audit remains empty.

### Compatibility and content boundary

All established root module paths remain available, including
`app.prompts.canonical_agent_prompts`, `app.prompts.react_prompts`, and the
specialized root modules used by the historical public surface. Each root
module now contains only imports and `__all__`; it has no prompt literals,
helper implementation, registry, manager, or second owner. `manager.py` keeps
the same keys, return values, formatting methods, and singleton entry point.

The migration moved the existing implementation files by path, changed only
package-relative/internal imports, and added compatibility exports. No prompt
literal was rewritten. The post-migration definition audit confirms each
canonical prompt is implemented once under `core`, `retrieval`, or `skills`.

## Task 0: non-Agent backend ownership baseline (2026-08-10)

Task 0 captured the ownership baseline for all 295 Python modules under `app/`
outside `agents/` and `prompts/`. The machine-readable map is
`config/backend_ownership.json`; the detailed static evidence is
`audit_output/backend-organization-2026-08-10/backend_ownership_baseline.md`.

The inventory records current/target owner, classification, replacement, and
retirement condition for every scoped module. It also freezes the route
registration surface, application router order, settings evidence, package
export review obligation, script-import review obligation, dynamic-import
findings, and monkeypatch/public compatibility audit requirement.

No file was moved or deleted. These paths remain deliberate Task 1 candidates
and are not removal approvals:

| Path | Current finding | Replacement / next owner | Removal condition |
| --- | --- | --- | --- |
| `app/graph/streaming.py` | Same-stem file/package collision | `app.graph.streaming` package | Empty app/scripts/tests/docs/config import/export/dynamic-load/monkeypatch audit plus register evidence. |
| `app/ingestion/loaders.py` | Same-stem collision and sibling-file dynamic loading | `app.ingestion.loaders.dispatch` | Dispatcher move and repeated full caller/dynamic-load audit. |
| `app/core/optimized_config.py` | No external runtime consumer in the baseline audit | `app.core.config` or no replacement | Repeated full-scope audit remains empty and deletion evidence is recorded. |
| `app/evaluation/service.py` | One of two ambiguously named evaluation owners | Explicit evaluation service owner after contract audit | Both contracts have named owners and no public caller depends on the ambiguous path. |
| `app/evaluation/services/evaluation_service.py` | Second evaluation owner with a distinct contract to verify | Explicit evaluation service owner after contract audit | Same as the preceding row; no merge is authorized by Task 0. |

The allowlist was extended with these five records. Each is an inventory
classification, not permission to delete. Tests and Git inspection/mutation
were not performed.

## Task 1: same-stem collisions and orphan-owner audit (2026-08-10)

### Ingestion loader dispatcher

Pre-move caller audit:

```text
rg -n --glob '*.py' '(from\s+app\.ingestion\.loaders|import\s+app\.ingestion\.loaders)' app scripts tests docs config
```

The concrete package callers were `app.api.routes.documents`,
`app.api.utils.document_helpers`, `app.services.auto_ingest_watcher`,
`app.services.parser_profiles`, and `scripts/document_toolkit.py`; tests and
development scripts also used the package's private loader seams. The package
initializer was the only production mechanism that dynamically loaded the
historical sibling `loaders.py`.

The dispatcher implementation now has one canonical owner at
`app.ingestion.loaders.dispatch`. `app.ingestion.loaders.__init__` is an
explicit package facade that preserves `load_documents`, extension constants,
loader aliases, private monkeypatch seams, and the existing `__all__` surface.
The old `app/ingestion/loaders.py` was deleted only after this audit; no
caller imported that file path as a module. The same post-move audit found no
`_loaders_impl`, sibling-file loader, or historical-file import, and
`Test-Path app/ingestion/loaders.py` returned `False`.

Static gate:

```text
conda run -n rag-local python -c <AST/JSON check for dispatch, package facade, and related owners>
TASK1A/B STATIC OK: 7 Python files; JSON OK
conda run -n rag-local ruff check --select E9,F63,F7,F82 <Task 1 changed Python files>
All checks passed!
```

### Graph streaming collision

`app/graph/streaming.py` contained only a compatibility import of
`encode_sse` and `run_query_stream`; the real package implementation and
public exports were already under `app.graph.streaming`. The read-only audit
found no direct import of the historical file path, while package imports from
API, orchestration, and tests resolve to the package. The inaccessible
same-stem file was deleted, `app.graph.streaming.__init__` was left as the
supported export surface, and `Test-Path app/graph/streaming.py` returned
`False`. The post-delete historical-file import audit was empty.

### Configuration and evaluation owners

`app/core/optimized_config.py` had no `app` or `scripts` caller in the fresh
pre-delete audit. The identical post-delete audit was empty and
`Test-Path app/core/optimized_config.py` returned `False`; its baseline record
now carries historical deletion status in `config/backend_ownership.json`.

The duplicate `Settings.query_rewrite_max_variants` declaration was reduced to
the previously effective declaration (`default=3`, alias
`QUERY_REWRITE_MAX_VARIANTS`). No configuration key or effective value was
changed.

The two evaluation contracts remain intentionally distinct and named here:

- `app.evaluation.service.EvaluationService` — retrieval-system evaluation
  over `RetrievalResult`, `EvaluationRun`, and the repository's aggregate
  metric DTOs; this is the public `app.evaluation` facade used by the API.
- `app.evaluation.services.evaluation_service.EvaluationService` — benchmark
  execution over retriever result dictionaries and `GroundTruth`, with
  configurable k-values and JSON result persistence; this is the CLI/benchmark
  service used by `scripts/run_evaluation.py`.

The `app.baselines` family remains the Chroma/object-oriented baseline
contract, while `app.evaluation.baselines` remains the runtime evaluation
retriever contract (including the API baseline). No baseline algorithms were
merged and no public evaluation import was removed.

Task 1 did not edit tests or execute tests. No Git inspection or mutation was
performed.

## Task 2: core/domain/schema and model-runtime ownership (2026-08-10)

The HTTP schema implementation now has one canonical owner at
`app.api.schemas.http`, with `app.api.schemas` as the package export surface.
`app.core.schemas` remains a module-object compatibility alias, so historic
imports and object identity continue to resolve to the same Pydantic classes.
The first-party API imports were updated to the canonical API schema package;
tests and documented historic imports were not edited.

The transport-independent exception hierarchy now has one canonical owner at
`app.domain.exceptions`. `app.core.exceptions` remains a module-object
compatibility alias. No HTTP conversion or exception behavior was moved into
the domain module.

The provider/model factory implementation now has one canonical owner at
`app.services.models.runtime`, with `app.services.models` as its package
boundary. `app.core.models` is a module-object compatibility alias to preserve
factory signatures, cache identity, imported private seams, and existing Agent
compatibility imports. Non-Agent first-party callers now import the canonical
service runtime; the remaining `app.core.models` callers are under
`app/agents`, which is explicitly outside this organization task.

Static checks:

```text
conda run -n rag-local python -c <AST over current non-Agent app modules>
TASK2 AST OK: 298 non-Agent modules
conda run -n rag-local ruff check --select E9,F63,F7,F82 <scoped backend>
All checks passed!
conda run -n rag-local python -c <canonical/legacy import identity assertions>
TASK2 COMPAT IMPORT IDENTITY OK
```

The compatibility allowlist now records the three retained core paths with
canonical replacement and evidence-based retirement conditions. No tests were
modified or run. No Git operation was performed.

## Task 3: graph knowledge and execution ownership (2026-08-10)

Graph knowledge infrastructure now has canonical owners under
`app.graph.knowledge`: `client.py` owns Neo4j lifecycle/query access,
`cypher_validation.py` owns query validation/templates, and
`entity_extraction.py` owns graph entity normalization/extraction/matching.
Graph execution now has canonical owners under `app.graph.execution`:
`state.py`, `workflow.py`, and `studio_entry.py`.

The historical root paths remain module-object compatibility aliases because
read-only tests, scripts, API/runtime services, and documented public seams
use them. First-party non-test callers were updated to canonical paths; the
aliases preserve exact class/function identity and monkeypatch targets. The
compatibility executor is the only retained workflow caller in production.
Nodes and routing now import the canonical execution state, and the canonical
knowledge client imports canonical Cypher validation. No graph algorithm,
query, state field, workflow result, or streaming contract was changed.

Static gate:

```text
conda run -n rag-local python -c <AST over current non-Agent app modules>
TASK3 AST OK: 306 non-Agent modules
conda run -n rag-local ruff check --select E9,F63,F7,F82 <Task 3 scope>
All checks passed!
conda run -n rag-local python -c <canonical/legacy graph identity assertions>
TASK3 COMPAT IMPORT IDENTITY OK
```

The six retained graph root paths and exact retirement conditions are recorded
in `config/refactor_cleanup_allowlist.json`. Tests were not modified or run;
no Git operation was performed.

## Task 4: ingestion ownership (2026-08-10)

The enhanced chunker now has one implementation split by responsibility:
`app.ingestion.chunking.classification`, `metadata`, and `splitter`. The
historical `app.ingestion.chunker_enhanced_clean` path is a compatibility facade
and retains the old public and private helper names.

The former `app.ingestion.utils` implementations were assigned explicit
canonical owners. OCR, charts, formulas, tables, layout, people, and vision
code live under `app.ingestion.extraction`; cleaning, structure, coreference,
performance, streaming, text structure, and monitoring code live under
`app.ingestion.processing`. The old utility modules are module-object aliases,
and `app.ingestion.utils` retains only compatibility exports.

First-party loader and ingestion-service imports use the canonical paths. The
canonical extraction/processing modules contain no imports of the historical
utility paths. Static gates passed:

```text
conda run -n rag-local python -c <AST over current non-Agent app modules>
TASK4 AST OK: 330 non-Agent modules
conda run -n rag-local ruff check --select E9,F63,F7,F82 app/ingestion app/services/ingest_service.py
All checks passed!
conda run -n rag-local python -c <canonical/legacy ingestion identity assertions>
TASK4 COMPAT IMPORT IDENTITY OK
```

Tests were not modified or run; no Git operation was performed.

## Task 7B checkpoint: API transport ownership (2026-08-10)

Canonical API transport owners are `app.api.transport.errors`,
`app.api.transport.responses`, and `app.api.transport.middleware`. Historical
`app.api.utils.error_responses`, `response_helpers`, and `app.api.middleware`
remain module-object compatibility aliases. SSE serialization/helper behavior,
middleware metrics, and public symbol identity were preserved.

```text
TASK7B AST OK: 63 API modules
All checks passed!
TASK7B COMPAT IMPORT IDENTITY OK
sol high read-only transport gate: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 7C checkpoint: API dependency ownership (2026-08-10)

Canonical dependency owners are `app.api.deps.auth`, `query`, `documents`,
`sessions`, `admin`, and `runtime`. Historical utility/runtime modules remain
module-object compatibility aliases; `app.api.dependencies` remains the
public aggregation facade. Route and SSE dependency semantics were preserved.

```text
TASK7C AST OK: 70 API modules
All checks passed!
TASK7C COMPAT IMPORT IDENTITY OK
sol high read-only dependency gate: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 8: pipeline, orchestration, MCP, and workflow boundary audit (2026-08-10)

The supported flow remains `API -> RAGPipeline -> OrchestrationEngine ->
canonical capability/compatibility executor`. No orchestration, pipeline, MCP,
or workflow module imports API internals. MCP server adapts Pipeline contracts;
the compatibility executor remains the historical workflow boundary. The
existing ownership is already aligned with the design, so no production source
move was made in this task.

Static gates:

```text
TASK8 REVIEW 3 PASS: no API imports from orchestration/pipeline/MCP/workflow
sol high read-only architecture gate: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 7 query checkpoint: API query and SSE ownership (2026-08-10)

The query implementation now has canonical owners under `app.api.query`:
request, response, execution, and streaming cache/execution/transport. The
historical `app.api.routes.query_*` modules remain module-object compatibility
aliases. Route assembly remains in `routes/query.py` and `routes/query_stream.py`;
the route handler names, response models, SSE event serialization, and route
registration files were preserved.

Static gates:

```text
TASK7 QUERY FINAL AST OK: 59 API modules
All checks passed!
TASK7 QUERY COMPAT IMPORT IDENTITY OK
sol high read-only route/SSE gate: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 6: services capability ownership (2026-08-10)

The services root is now a compatibility boundary. Canonical implementations
are grouped under:

- `app.services.models`: catalog, configuration, and provider runtime
- `app.services.runtime`: request context, queues, resilience, retries, and runtime state
- `app.services.observability`: tracing, alerts, logs, and execution tracking
- `app.services.documents`, `sessions`, and `language`
- `app.services.query` and `retrieval`
- `app.services.security`: admin security, authorization, network validation,
  redaction, quota, and rate limiting

The rule-based rewrite owner is `app.services.query.rule_rewrite`; the LLM
rewrite owner is `app.services.query.llm_rewriter`. They were not merged.
Non-Agent first-party imports use canonical paths. Historical root service
paths contain only module-object compatibility aliases; the aliases and their
retirement conditions are recorded in `config/refactor_cleanup_allowlist.json`.

Static gates:

```text
TASK6 STATIC AST OK: 410 non-Agent modules
All checks passed!
TASK6 COMPAT IMPORT IDENTITY OK
TASK6 ARCHITECTURE GATE OK: aliases/canonical/separation/accidental-root checks
sol high read-only architecture gate: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 5: retrieval, evaluation, baselines, tools, and advanced models (2026-08-10)

Retriever storage implementations now have canonical owners at
`app.retrievers.stores.vector`, `stores.corpus`, and `stores.parent`; the
hybrid executor is canonical at `app.retrievers.hybrid.retriever`. The old
flat retriever modules are module-object compatibility aliases. Vector/BM25
fusion, reranking, cache keys, parent expansion, and fallback code were not
merged or reordered.

The Chroma/object-oriented baseline family now lives under
`app.evaluation.baselines.chroma`. It remains distinct from the runtime-global
retriever baseline family under `app.evaluation.baselines`; the two
`EvaluationService` contracts remain separate and explicitly documented.

Graph tools/config and web search now have canonical owners under
`app.tools.graph` and `app.tools.web`. Advanced RAG Pydantic DTOs now have the
transport-independent canonical owner `app.domain.advanced_rag`. Historical
tool, model, and baseline paths remain logic-free compatibility aliases.

Static gates passed:

```text
TASK5 AST OK: 335 non-Agent modules
TASK5 COMPAT IMPORT IDENTITY OK
TASK5B AST OK: 346 non-Agent modules
All checks passed!
TASK5B COMPAT IMPORT IDENTITY OK
```

Tests were not modified or run; no Git operation was performed.

## Task 9: package exports, compatibility governance, and documentation (2026-08-10)

Canonical examples in the backend documentation were updated for ingestion,
retriever, service, and API query paths. Compatibility aliases remain recorded
with owner, replacement, evidence, and retirement condition in
`config/refactor_cleanup_allowlist.json`; ownership checkpoints are recorded in
`config/backend_ownership.json`. No wildcard export redesign or public import
removal was made.

sol high read-only documentation/compatibility gate: PASS.

## Task 7A checkpoint: application construction (2026-08-10)

Application construction now has canonical owners under
`app.api.application`: `factory.py`, `lifespan.py`, `router_registry.py`, and
`static_files.py`. `app.api.main` remains the stable `app` entry and keeps the
historical frontend symbols, route/helper compatibility facade, and
monkeypatch propagation bridge. Middleware registration order, lifespan
startup/shutdown behavior, router registration order, static mounts, and
frontend fallback paths were preserved. No duplicate route/business
implementation was retained in `main.py`.

Static gates:

```text
TASK7A AST OK: 75 API modules
All checks passed!
TASK7A COMPAT MODULES=24 ROUTERS=21
TASK7A route registry order preserved
sol high read-only application gate: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 7D: route grouping (2026-08-10)

Canonical route owners now span `app.api.routes.public`, `admin`,
`operations`, and `compatibility`. All 23 old flat route modules are
module-object compatibility aliases; the registry imports only canonical
modules. URL/method/tag/dependency/response/SSE contracts and handler/router
identity were preserved. The duplicate `/admin/ops/rollback` route was removed
from `admin.ops`; `admin.settings` is the sole owner.

```text
TASK7D FULL AST OK: 461 non-Agent modules
TASK7D REGISTRY COUNTS: ROUTERS=21, COMPAT=24
TASK7D ROUTE DUPLICATE GATE PASS: 137 routes, 0 duplicate method/URL pairs
TASK7D FINAL IDENTITY OK: 23 route pairs
TASK7D FINAL SAME-STEM PASS
TASK7D FINAL DYNAMIC LOADER PASS
sol high full route-group review: PASS
```

Tests were not modified or run; no Git operation was performed.

## Task 7E checkpoint: oversized route extraction audit (2026-08-10)

The rollback capability already has the canonical service owner
`app.services.runtime.runtime_ops`; the sole HTTP route owner is
`app.api.routes.admin.settings.admin_ops_rollback`. The duplicate route in
`admin.ops` was removed during Task 7D. Settings reload was intentionally not
moved: it rebuilds singleton objects held by `app.api.dependencies`, and moving
that mutation into a service would create a reverse services-to-API dependency
or change query/SSE runtime semantics. This is the only deferred Task 7E
boundary; the remaining oversized route responsibilities were completed in
the four slices below.

### Completed Task 7E slices

- `admin_ops`: benchmark, replay, overview/runtime/alerts aggregation, health
  probing, and log-level operations use canonical runtime/observability owners;
  replay preserves the existing Pipeline → Orchestration execution boundary.
- `documents`: upload storage, hash/deduplication, registry/index actions,
  source binding, visibility inputs, queue freshness, and health use the
  canonical document/runtime owners.
- `auth`: local auth, profile/password operations, OAuth state TTL and atomic
  one-time consumption, Google identity upsert, and session creation use the
  canonical auth owners.
- `admin_settings`: model settings and user API settings use canonical model
  services; rollback remains owned by `runtime_ops` and reload remains deferred
  for singleton-semantics preservation.

The final constrained review found no route Agent/Workflow construction, no
services-to-API reverse dependency, no duplicate rollback owner, and no
Pipeline/Orchestration bypass in the completed slices. Final static gates were
`TASK7E AST OK: 589 app modules` and
`ruff check --select E9,F63,F7,F82 app`: passed. Tests were not modified or
run; no Git operation was performed.

sol/terra high constrained Task 7E review: no safe behavior-preserving owner
was available for reload under the current scope. Tests were not modified or
run; no Git operation was performed.

## Task 10: current migration checkpoint verification (2026-08-10)

Final read-only gates passed:

```text
TASK10 CHECKPOINT AST OK: 461 non-Agent app modules
All checks passed!
TASK10 SAME-STEM GATE PASS: no file/package stem collisions
TASK10 MOVED SERVICES ROOT GATE PASS
TASK10 ROUTE AUDIT: all router/include lines=159; main include order lines=265-285 preserved
TASK10 CORE LEGACY CALLER GATE PASS
```

The only remaining `__import__` is runtime module resolution in
`app/graph/streaming/safe_wrappers.py`; no sibling-file loader remains. Git
verification was intentionally skipped per user instruction. This is a
final static migration checkpoint. Runtime/test verification remains deferred
because tests were not modified or run, and Git verification was intentionally
skipped per user instruction.

## Follow-up directory review: auth/connectors/documents/language (2026-08-11)

This checkpoint records the additional non-Agent backend directory review
requested after the Task 0–10 closure. Luna implemented only evidence-backed
changes in disjoint directory scopes; Sol performed read-only architecture
reviews. Existing public imports and compatibility facades remain in place.

- `app/services/auth`: `legacy_service.py` remains a compatibility service for
  the historical JSON format and eight-character password policy. It now reuses
  canonical time, validation, and PBKDF2 helpers. `auth_db.py` remains a pure
  compatibility import for the single SQLite `AuthDBService` owner.
- `app/services/connectors`: contracts, metadata, credentials, and management
  boundaries were retained. `__init__.py` now exposes the verified public types
  and repositories; `management.py` was not mechanically split.
- `app/services/documents`: ingestion, index lifecycle, registry, deduplication,
  scope, and health boundaries were retained. Scope output is stable and health
  counters tolerate `OverflowError` in malformed historical records.
- `app/services/language`: the query preprocessor now imports the canonical
  `app.services.query.synonyms` owner directly. Root-level Chinese/language
  modules remain compatibility wrappers, and the package stays lightweight.

Static evidence:

```text
LUNA DIRECTORY SLICES: auth/connectors/documents/language complete
SOL REVIEW: auth PASS; documents PASS after OverflowError fix;
            language PASS; connectors PASS
AST/Ruff targeted checks: passed
Tests: not run; Git: not run
```

Deferred risks are recorded rather than hidden: the legacy JSON auth service
retains weaker historical security semantics and is not a production API owner;
connector credentials are process-memory backed and metadata/credential writes
are not cross-repository transactions; the duplicate `安全` synonym key is a
pre-existing canonical data issue. These require separate behavior/test scope.

## Agent/workflow/pipeline architecture audit (2026-08-11)

Read-only architecture audit registered at
`audit_output/backend-organization-2026-08-10/agent-workflow-pipeline-architecture-audit-2026-08-11.md`.
It reviewed the Agent, LangGraph, workflow, Pipeline, orchestration, relevant
services, API routes, configuration, and compatibility boundaries without
running tests or Git commands and without modifying production code.

The production query entry boundary remains intact:

```text
API → RAGPipeline → OrchestrationEngine → LegacyWorkflowCompatibilityExecutor
    → standard graph | strict workflow | advanced workflow
```

No compatibility module is approved for removal by this audit. In particular,
`app.graph.workflow`, `app.agents.enhanced_rag_workflow`, validation/context
aliases, and legacy synthesis adapters still preserve production compatibility,
lifespan, monkeypatch, test, script, or documented-public import surfaces.
Their existing `remove_when` conditions in
`config/refactor_cleanup_allowlist.json` remain mandatory.

The audit found must-fix execution-contract issues before any retirement work:

- strict-quality context storage is keyed only by `session_id`, including the
  public default `"default"`, without user ownership validation;
- strict and SSE paths can invoke synchronous retrieval/generation from async
  execution contexts;
- strict workflow lacks explicit `web`/`react` retrieval execution and approves
  validation failures through a degraded `is_valid=True` result;
- `GraphState` omits the actively read/written `execution_id` field;
- standard normal, streaming, and ReAct paths have non-equivalent final quality
  processing; and
- retry/circuit-breaker policy has more than one owner/default.

Static checks: AST parsed 600 `app` Python files with `utf-8-sig` and zero
syntax errors; 137 route declarations had zero duplicate complete
method/path pairs; 10 LangGraph `add_node` calls had no duplicate node name;
and no static `services/agents/workflow/graph/orchestration/pipeline → app.api`
import was found. Ruff could not be reproducibly run in the mandated
`rag-local` environment, so this is not a lint-pass record. Runtime behavior,
retry multiplication, external imports, and compatibility retirement remain
unconfirmed until separately authorized tests/import audits are run.

## Typed orchestration cutover progress (2026-08-11)

The default public call path is now:

```text
API / SSE / MCP → RAGPipeline → typed OrchestrationEngine → canonical capabilities → FinalizationService
```

`FinalizationService` owns grounding, safety, validation, and policy-gated
quality reporting. Validation exceptions produce
`ValidationStatus(state="degraded", approved=False)`; no typed terminal path
manufactures an approved validation result. Standard, strict-quality, and
advanced profiles select `ExecutionPolicy` on one Engine rather than a
workflow factory. SSE is an Engine event adapter with terminal answer,
citations, route, validation, grounding, safety, and execution metadata.

Static audit after the cutover found no production reference to a legacy
executor or compatibility capability in `app/pipeline`, `app/api`, or
`app/mcp`. These files remain retained because dynamic aliases, historical
imports, or test patch targets still exist:

- `app/orchestration/compatibility_executor.py`
- `app/orchestration/compatibility_capabilities.py`
- `app/workflow/enhanced_rag_workflow.py`
- `app/workflow/advanced_rag_workflow.py`
- `app/graph/streaming/stream_processor.py`

No file was deleted. Shadow rollout remains disabled by
`config/orchestration_rollout.json`; later removal requires its runtime
observation window and a fresh caller/dynamic-import/export audit.
