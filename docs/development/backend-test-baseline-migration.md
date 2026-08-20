# Backend test baseline migration inventory

## Frozen collection baseline

The baseline was collected with `.venv\\Scripts\\python.exe -m pytest --collect-only -q` on 2026-08-20: **1386 collected items / 47 collection errors** (15.42s, exit 1).  This matches the approved baseline.  The rows below record the first collection failure for every error file, a current backend owner, and the bounded next action.  They are inventory evidence only; no production code or test was changed.

Dependency probe:

```
{'mcp': False, 'jieba': False, 'psutil': False, 'pandas': False}
No broken requirements found.
```

`pyproject.toml` declares `jieba`, `psutil`, and `mcp`; they are absent from this virtual environment. `pandas` and the `fitz` provider (`PyMuPDF`) are absent as well and must be resolved before their current multimodal tests can collect.

## Task 2 environment repair (2026-08-20)

The declared `.venv` test environment was installed with `.[dev,multimodal]` after adding the `multimodal` optional extra (`pandas`, `PyMuPDF`, `pdfplumber`, and `tabulate`) and including it in `full`. The import probe for `jieba`, `mcp`, `pandas`, `psutil`, `fitz`, `pdfplumber`, and `tabulate` passed, and `pip check` reported no broken requirements.

The same full collection command now reports **1478 collected items / 37 collection errors** (17.38s, exit 1), down from the frozen 47-error baseline. The remaining collection errors are the documented retired-path and chart-extractor migrations; this environment-only task made no behavioral or assertion changes. The eight focused files now collect 79 tests, with 66 passing, 1 skipped, and 12 current-contract/runtime failures (including optional `docling` absence), rather than import failures.

## Retirement and ownership evidence

* `d1075732` explicitly deleted 14 legacy agent compatibility wrappers and added the typed router modules.
* `54192131` explicitly deleted 26 further agent wrappers, including fact verification, hallucination patterns, route accuracy, calibration, result schemas, and validation cascade wrappers.
* `5d05e6f5` explicitly removed the LangGraph system (`app.graph.workflow`, `state`, `nodes`, streaming wrappers/processor) while retaining the current knowledge package.
* `e322be7e` removed obsolete RAG workflows and router compatibility; `ccbaec34` then removed the last legacy workflow test.
* The required active-dependency scan returned **no matches**:
  `rg -n "app\\.(agents|graph)\\.(answer_validator_agent|router_agent|vector_rag_agent|graph_rag_agent|react_agent|synthesis_agent|workflow|state|nodes)" app --glob "*.py"`.
  Thus historic strings do not establish a current dependency.

## Task 3 context-contract disposition (2026-08-20)

`tests/agents/test_context_tracker.py` now exercises the tenant-scoped
`app.services.sessions.context_tracker` store through `(user_id, session_id)`
lookups. The migrated coverage retains history limits, entity and topic
tracking, routing hints, TTL cleanup, English and Chinese reference resolution,
and explicit cross-user isolation. `_detect_intent` is called by
`update_conversation_context`; `_detect_reference_pronouns` is called by the
public routing-hint and follow-up paths; and `resolve_query_with_context`
documents both English and Chinese behavior. Their Chinese assertions therefore
remain current canonical contract coverage. The restored suite reports **26
passed / 5 failed**: Chinese resolution, navigation/comparison/clarification
intent, and pronoun detection are live context-service defects assigned to Task
7. Only `_is_followup_query("它有什么特点?", context)` remains excluded because
the seven-character input returns at the unconditional `<30`-character branch
before pronoun detection, so that assertion tested no Chinese behavior.

## Task 3 validation/router/config/synthesis migration (2026-08-20)

All 18 Task 3 files now collect from their canonical backend owners: **350
items collected**. The focused execution reports **334 passed / 16 failed**
(68.66s). Root-cause tracing assigns 5 failures to the live canonical context
service and 11 to external gates, without changing production behavior or
weakening assertions:

| gate | focused failures | observed boundary |
| --- | ---: | --- |
| canonical context service | 5 | Chinese resolution, three intent categories, and pronoun detection fail in the active owner; assigned to Task 7 |
| validation NLI model | 1 | Hugging Face model access is blocked; the deterministic lexical fallback returns the documented conservative issue |
| relevance scoring | 3 | configured Ollama runtime is not running; the canonical scorer returns its `0.5/somewhat_relevant` error fallback |
| router accuracy samples | 3 | OpenAI credentials are absent; canonical routing returns its safe vector fallback |
| synthesis citation generation | 4 | OpenAI credentials are absent; canonical synthesis returns its service-unavailable fallback |

The other **334 focused assertions pass**, including 26 tenant-scoped context
tests, 18 cache-isolated router fallback tests, and 24 shared
base/config/utils/vector tests. The canonical vector imports in
`test_unified_agents.py` target `app.agents.rag.vector`, and its patches target
the lookup in that module.

The required repository-wide retired-path scan still reports matches only in
files outside Task 3 (notably the separately inventoried resilience, session
language, weight-optimization, and synthesis-agent suites); the 18 Task 3
paths have no matches. The fresh full collection command reports **1826
collected items / 19 collection errors** (19.56s), with all 19 errors outside
this task's file list.

## Task 4 RAG/ReAct/scope/resilience/query/web/weight migration (2026-08-20)

The seven Task 4 files plus the dedicated current streaming suite collect **109 tests**. Focused
execution reports **97 passed / 1 failed / 1 skipped**. The remaining failure,
`test_local_evidence_model_does_not_expose_memory_context`, is a live canonical
`LocalEvidenceChatModel` defect: the no-evidence response is mojibake rather
than the asserted Chinese message, while the test still proves memory text is
not exposed. It remains visible for Task 7. The one skip is the pre-existing
real-LLM ReAct integration gate.

ReAct patches target `app.agents.tool.react`, where models and RAG/synthesis
functions are looked up, and graph fixtures now use the canonical string entity
list. Scope tests alias the active `rag.graph` and `rag.vector` module objects.
Query expansion patches `rag.vector` at construction-time dependency lookups.
Web integration behavior now patches `rag.web.search_web`; no focused test makes
a live network call. Quality scoring imports `validation.quality_orchestrator`
and reloads both shared configuration and the consuming orchestrator when
testing environment-provided weights.

Eight resilience functions were deleted individually because their sole
subject was `app.graph.streaming.stream_processor`, explicitly deleted by
`5d05e6f5` when service orchestration replaced LangGraph streaming:
`test_stream_prefers_effective_hit_count_for_web_fallback`,
`test_stream_does_not_use_web_when_fallback_enabled_and_local_evidence_sufficient`,
`test_stream_emits_thought_events`,
`test_stream_continues_when_vector_retrieval_fails`,
`test_stream_forces_web_when_user_explicitly_requests_online_search`,
`test_stream_skips_web_for_casual_chat`,
`test_stream_recovers_when_stream_synthesis_raises`, and
`test_stream_partial_then_error_emits_answer_reset`. Current router fallback,
vector normalization, synthesis fallback, citation, strict-review, and local
evidence resilience assertions remain in the file.

`test_correlation_calculation` and `test_ab_testing_script_exists` were removed
because their only owner, the development-only `scripts/test_quality_weights.py`,
was explicitly deleted by `828aa796`; current/alternative weighted scoring and
the sum-to-one boundary remain covered against the canonical orchestrator.

The required retired-path scan has no matches in the seven Task 4 files. Its
repository-wide results are confined to separately inventoried Task 5/6 files.
Fresh full collection reports **1958 collected items / 12 collection errors**
(17.73s); every error is outside Task 4.

## 47-file matrix

| test file | missing import/dependency | retirement evidence | current owner | action | focused verification |
| --- | --- | --- | --- | --- | --- |
| `tests/agents/test_answer_validator.py` | `app.agents.answer_validator_agent` | `d1075732` deleted wrapper | `app.agents.validation.public`; NLI helpers in `validation.nli` | migrated | passes focused current-contract execution |
| `tests/agents/test_answer_validator_cascade.py` | `app.agents.validation_cascade` | `54192131` deleted wrapper | `app.agents.validation.cascade` | migrated / external gate | collects; one NLI-model gate remains explicit |
| `tests/agents/test_context_tracker.py` | `app.agents.context_tracker_agent` | `d1075732` deleted wrapper | `app.services.sessions.context_tracker` | migrated / Task 7 defect | 31 collect; 26 pass and 5 live Chinese contract failures remain visible |
| `tests/agents/test_fact_verification.py` | `app.agents.fact_verification` | `54192131` deleted wrapper | `app.agents.validation.fact_verification` | migrated | passes focused current-contract execution |
| `tests/agents/test_hallucination_detection.py` | `app.agents.hallucination_patterns` | `54192131` deleted wrapper | `app.agents.validation.hallucination_patterns` | migrated | passes focused current-contract execution |
| `tests/agents/test_quality_orchestrator.py` | `app.agents.quality_orchestrator_agent` | `d1075732` deleted wrapper | `app.agents.validation.quality_orchestrator` | migrated | passes focused current-contract execution |
| `tests/agents/test_react_agent_tools.py` | `app.agents.react_agent` | `d1075732` deleted wrapper | `app.agents.tool.react` | migrated | canonical tool lookup patches and string-entity fixtures pass |
| `tests/agents/test_relevance_scoring.py` | `app.agents.relevance_scoring` | `54192131` deleted wrapper | `app.agents.rag.relevance` | migrated / external gate | collects; three live-Ollama semantic cases remain explicit |
| `tests/agents/test_retrieval_quality.py` | `app.agents.retrieval_quality_agent` | `d1075732` deleted wrapper | `app.agents.rag.retrieval_quality` | migrated | passes focused current-contract execution |
| `tests/agents/test_route_accuracy.py` | `app.agents.route_accuracy_tracker` | `54192131` deleted wrapper | `app.agents.router.accuracy`, `router.routing.LegacyRouteDecision` | migrated | compatibility fixture matches current routing dataclass; passes |
| `tests/agents/test_route_validator.py` | `app.agents.route_validator_agent` | `d1075732` deleted wrapper | `app.agents.router.validator`, `router.routing.LegacyRouteDecision` | migrated | patches/current dataclass pass |
| `tests/agents/test_router_accuracy.py` | `app.agents.router_agent` | `d1075732` deleted wrapper | `app.agents.router.routing` | migrated / external gate | collects; three credentialed accuracy samples remain explicit |
| `tests/agents/test_router_calibration.py` | `app.agents.router_calibration` | `54192131` deleted wrapper | `app.agents.router.calibration` | migrated | passes focused current-contract execution |
| `tests/agents/test_router_calibration_integration.py` | `app.agents.router_agent` | `d1075732` deleted wrapper | `app.agents.router.routing`, `app.agents.router.calibration` | migrated | patch lookup sites pass |
| `tests/agents/test_router_enhanced.py` | `app.agents.router_examples` | `54192131` deleted wrapper | `app.agents.router.examples` | migrated | passes focused current-contract execution |
| `tests/agents/test_router_fallback.py` | `app.agents.router_agent` | `d1075732`, `54192131`, and `e322be7e` removed wrapper paths | `app.agents.router.routing`, `app.agents.shared.config` | migrated | 18 deterministic cache-isolated fallback tests pass |
| `tests/agents/test_synthesis_citation.py` | `app.agents.synthesis_agent` | `d1075732` deleted wrapper | `app.agents.synthesizer.generation`, `templates` | migrated / external gate | collects; four credentialed generation cases remain explicit |
| `tests/graph/test_critical_fixes.py` | `app.graph.neo4j_client` | `5d05e6f5` moved legacy graph layout | `app.graph.knowledge.client`, `app.agents.rag.graph` | migrate | collect after split-client/RAG remap |
| `tests/graph/test_cypher_validation.py` | `app.graph.cypher_validation` | `5d05e6f5` deleted old module | `app.graph.knowledge.cypher_validation` | migrate | collect Cypher validation tests |
| `tests/graph/test_graph_rag_validation.py` | `app.agents.graph_rag_agent` | `d1075732` deleted wrapper | `app.agents.rag.graph` | migrate | collect graph-RAG validation tests |
| `tests/integration/test_batch_chart_extraction.py` | `app.ingestion.extraction.chart_extractor` | current `charts_batch` still names old sibling | `app.ingestion.extraction.charts` (called by `pdf_chart_loader`) | repair-test-import | collect after targeting current chart extractor API |
| `tests/integration/test_session_language_tracking.py` | `app.graph.nodes` | `5d05e6f5` removed graph nodes/state | `app.services.sessions.language` | migrate | collect equivalent session-language service coverage |
| `tests/integration/test_streaming_pdf.py` | `psutil` | declared in `pyproject.toml`; absent in probe | `app.ingestion.utils.streaming_pdf_loader` | install-dependency | install sync, then collect this file |
| `tests/mcp/test_server_contracts.py` | `mcp` | declared in `pyproject.toml`; absent in probe | `app.mcp.server`, `app.mcp.contracts` | install-dependency | install sync, then collect MCP contracts |
| `tests/mcp/test_server_transport.py` | `mcp` | declared in `pyproject.toml`; absent in probe | `app.mcp.server` | install-dependency | install sync, then collect MCP transport |
| `tests/performance/test_batch_benchmarks.py` | `psutil` | declared in `pyproject.toml`; absent in probe | `tests.performance.benchmark_pdf_processing` (called by `tests.performance.run_all_benchmarks`) | install-dependency | install sync, then collect benchmarks |
| `tests/performance/test_benchmarks.py` | `psutil` | declared in `pyproject.toml`; absent in probe | `tests.performance.benchmark_pdf_processing` (called by `tests.performance.run_all_benchmarks`) | install-dependency | install sync, then collect benchmarks |
| `tests/retrievers/test_query_expansion_integration.py` | `app.agents.vector_rag_agent` | `d1075732` deleted wrapper | `app.agents.rag.vector`, `app.retrievers.query_expansion` | migrated | expansion, disabled, fallback, ratio, filtering, and retrieval-quality cases pass |
| `tests/services/multimodal/test_image_processor.py` | `fitz` | current processor remains an active multimodal owner | `app.services.multimodal.image_processor` | install-dependency | install PyMuPDF provider, then collect image processor |
| `tests/services/multimodal/test_table_extractor.py` | `pandas` | current processor remains an active multimodal owner | `app.services.multimodal.table_extractor` | install-dependency | install pandas, then collect table extractor |
| `tests/test_agent_resilience.py` | `app.agents.router_agent` plus fake retired `sys.modules` patchpoints | `d1075732` deleted agent wrappers; `5d05e6f5` deleted `stream_processor` | `app.agents.router.routing`, `app.agents.rag.vector`, `app.agents.synthesizer.generation`; streaming behavior in typed pipeline/API suites | migrated / Task 7 defect; eight stream behaviors mapped to active seams | current fallback/normalization/review assertions pass; one live LocalEvidence Chinese-encoding defect remains visible |
| `tests/test_agent_scope_filtering.py` | `ImportError: cannot import name 'graph_rag_agent' from 'app.agents'` | `d1075732` deleted wrappers | `app.agents.rag.graph`, `app.agents.rag.vector` | migrated | module-alias monkeypatches preserve explicit/class scope intersections |
| `tests/test_batch_chart_extractor.py` | `app.ingestion.extraction.chart_extractor` | current `charts_batch` still names old sibling | `app.ingestion.extraction.charts` | repair-test-import | collect after targeting current chart extractor API |
| `tests/test_graph_rag_agent_enhanced.py` | `app.agents.graph_rag_agent_enhanced` | `54192131` deleted wrapper | `app.agents.rag.enhanced_graph` | migrate | collect entity extraction tests |
| `tests/test_graph_rag_optimization.py` | `app.agents.graph_rag_agent` | `d1075732`/`54192131` deleted wrappers | `app.agents.rag.graph`, `app.agents.rag.enhanced_graph`, `app.agents.rag.cache` | migrate | collect split graph-RAG/cache tests |
| `tests/test_neo4j_delete_by_source.py` | `app.graph.neo4j_client` | `5d05e6f5` deleted old path | `app.graph.knowledge.client` | migrate | collect `Neo4jClient` deletion behavior |
| `tests/test_react_agent.py` | `app.agents.react_agent` | `d1075732` deleted wrapper | `app.agents.tool.react` | migrated / external gate | canonical model/tool/synthesis lookup patches pass; real-LLM integration remains explicit |
| `tests/test_streaming_analytics_logging.py` | `app.graph.streaming.safe_wrappers` | `5d05e6f5` removed wrappers | `app.api.query.streaming.execution`, retrieval logger | migrate | collect analytics at current streaming boundary |
| `tests/test_streaming_react_agent_class.py` | `app.graph.streaming.stream_processor` | `5d05e6f5` removed processor | `app.api.query.streaming.execution`, `app.agents.tool.react` | migrate | collect streaming agent-class propagation |
| `tests/test_weight_optimization.py` | `app.agents.quality_orchestrator_agent`; deleted A/B helper script | `d1075732` deleted wrapper; `828aa796` deleted development test script | `app.agents.validation.quality_orchestrator`, `app.agents.shared.config` | migrated; two missing-script tests restored and visibly failing for Task 7 | current/alternative weighting and sum-to-one boundary pass; missing A/B owner remains visible |

| `tests/test_workflow_fixes.py` | `app.graph.workflow` | `5d05e6f5` removed LangGraph workflow; `ccbaec34` removed last legacy workflow test | none; supported orchestration is not that public API | delete-retired-contract | confirm each assertion is only a removed workflow helper contract |
| `tests/unit/test_chinese_document_indexer.py` | `jieba` | declared in `pyproject.toml`; absent in probe | `app.services.language.chinese_document_indexer` | install-dependency | install sync, then collect indexer tests |
| `tests/unit/test_chinese_query_preprocessor.py` | `jieba` | declared in `pyproject.toml`; absent in probe | `app.services.language.chinese_query_preprocessor` | install-dependency | install sync, then collect preprocessor tests |
| `tests/unit/test_chinese_tokenizer.py` | `jieba` | declared in `pyproject.toml`; absent in probe | `app.services.language.chinese_tokenizer` | install-dependency | install sync, then collect tokenizer tests |
| `tests/unit/test_synthesis_language.py` | `app.agents.synthesis_agent` | `d1075732` deleted wrapper | `app.agents.synthesizer.generation` | migrated | canonical lookup patches pass |
| `tests/unit/test_unified_agents.py` | `base_agent`, `unified_config`, `shared_utils` wrappers | `d1075732`/`54192131` deleted wrappers | `app.agents.shared.base`, `config`, `utils`, `result_schemas`; `app.agents.rag.vector` | migrated | 24 current shared/vector contract tests pass |
| `tests/unit/test_web_research_agent.py` | `app.agents.web_research_agent` | `d1075732` deleted wrapper | `app.agents.rag.web`, `app.agents.rag.web_utils` | migrated | 37 utility/integration cases pass through deterministic `search_web` seam |

### Task 4 streaming behavior mappings

| Old test | Active production seam and observable current contract |
|---|---|
| `test_stream_prefers_effective_hit_count_for_web_fallback` | `RAGAgentService.retrieve/_enabled_retrievers`: web execution is route-capability-owned now; a web-capable route invokes web and fuses its evidence even when vector diagnostics report zero effective hits |
| `test_stream_does_not_use_web_when_fallback_enabled_and_local_evidence_sufficient` | `RAGAgentService.retrieve/_enabled_retrievers`: a RAG-only route never invokes web and returns local evidence; the retired hit-threshold selection is no longer active |
| `test_stream_emits_thought_events` | `RAGPipeline.execute_stream` → `OrchestrationEngine.execute_stream`: the active seam emits no thought events; the restored behavioral assertion stays visibly failing as a Task 7 contract gap (status frames are not claimed as replacement coverage) |
| `test_stream_continues_when_vector_retrieval_fails` | `RAGAgentService.retrieve`: BM25 evidence survives vector failure; public typed skipped/completed degradation statuses are emitted without asserting private error text |
| `test_stream_forces_web_when_user_explicitly_requests_online_search` | `query_stream` → `prepare_standard_request`: explicit web selection is now the request flag, which policy preserves for non-smalltalk requests |
| `test_stream_skips_web_for_casual_chat` | `query_stream` → `prepare_standard_request`: smalltalk policy clears web and reasoning before pipeline execution |
| `test_stream_recovers_when_stream_synthesis_raises` | `stream_execution_events` → `RAGPipeline.execute_stream` → engine: synthesis failure now becomes a safe `internal_error` SSE with no false done event, replacing fallback-answer recovery |
| `test_stream_partial_then_error_emits_answer_reset` | `stream_execution_events`: a real partial chunk followed by a pipeline exception is forwarded as `answer_chunk`, then safe `internal_error`, with no done event; the retired answer-reset recovery contract no longer exists |

`test_correlation_calculation` and `test_ab_testing_script_exists` are restored.
There is no current owner for `scripts.test_quality_weights`; both failures stay
visible and are classified for Task 7. The canonical `shared.quality_models`
import is part of the self-contained Task 4 head.

## Matrix review

The matrix contains exactly 47 data rows. Each brief-listed path appears once. Every owner above was verified as a current backend module (and, where stated, by a current caller); every retirement conclusion cites an explicit removal commit rather than file absence alone. The only live legacy-path scan prescribed by the task returned no results.
