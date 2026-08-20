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

## 47-file matrix

| test file | missing import/dependency | retirement evidence | current owner | action | focused verification |
| --- | --- | --- | --- | --- | --- |
| `tests/agents/test_answer_validator.py` | `app.agents.answer_validator_agent` | `d1075732` deleted wrapper | `app.agents.validation.public`; NLI helpers in `validation.nli` | migrated | passes focused current-contract execution |
| `tests/agents/test_answer_validator_cascade.py` | `app.agents.validation_cascade` | `54192131` deleted wrapper | `app.agents.validation.cascade` | migrated / external gate | collects; one NLI-model gate remains explicit |
| `tests/agents/test_context_tracker.py` | `app.agents.context_tracker_agent` | `d1075732` deleted wrapper | `app.services.sessions.context_tracker` | migrated / Task 7 defect | 31 collect; 26 pass and 5 live Chinese contract failures remain visible |
| `tests/agents/test_fact_verification.py` | `app.agents.fact_verification` | `54192131` deleted wrapper | `app.agents.validation.fact_verification` | migrated | passes focused current-contract execution |
| `tests/agents/test_hallucination_detection.py` | `app.agents.hallucination_patterns` | `54192131` deleted wrapper | `app.agents.validation.hallucination_patterns` | migrated | passes focused current-contract execution |
| `tests/agents/test_quality_orchestrator.py` | `app.agents.quality_orchestrator_agent` | `d1075732` deleted wrapper | `app.agents.validation.quality_orchestrator` | migrated | passes focused current-contract execution |
| `tests/agents/test_react_agent_tools.py` | `app.agents.react_agent` | `d1075732` deleted wrapper | `app.agents.tool.react` | migrate | collect tool-react tests |
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
| `tests/retrievers/test_query_expansion_integration.py` | `app.agents.vector_rag_agent` | `d1075732` deleted wrapper | `app.agents.rag.vector`, `app.retrievers.query_expansion` | migrate | collect query-expansion integration |
| `tests/services/multimodal/test_image_processor.py` | `fitz` | current processor remains an active multimodal owner | `app.services.multimodal.image_processor` | install-dependency | install PyMuPDF provider, then collect image processor |
| `tests/services/multimodal/test_table_extractor.py` | `pandas` | current processor remains an active multimodal owner | `app.services.multimodal.table_extractor` | install-dependency | install pandas, then collect table extractor |
| `tests/test_agent_resilience.py` | `app.agents.router_agent` | `d1075732` deleted wrapper | `app.agents.router.routing`, `app.agents.synthesizer.generation`, API streaming | migrate | collect resilience tests against current boundaries |
| `tests/test_agent_scope_filtering.py` | `ImportError: cannot import name 'graph_rag_agent' from 'app.agents'` | `d1075732` deleted wrappers | `app.agents.rag.graph`, `app.agents.rag.vector` | migrate | collect scoped retrieval tests |
| `tests/test_batch_chart_extractor.py` | `app.ingestion.extraction.chart_extractor` | current `charts_batch` still names old sibling | `app.ingestion.extraction.charts` | repair-test-import | collect after targeting current chart extractor API |
| `tests/test_graph_rag_agent_enhanced.py` | `app.agents.graph_rag_agent_enhanced` | `54192131` deleted wrapper | `app.agents.rag.enhanced_graph` | migrate | collect entity extraction tests |
| `tests/test_graph_rag_optimization.py` | `app.agents.graph_rag_agent` | `d1075732`/`54192131` deleted wrappers | `app.agents.rag.graph`, `app.agents.rag.enhanced_graph`, `app.agents.rag.cache` | migrate | collect split graph-RAG/cache tests |
| `tests/test_neo4j_delete_by_source.py` | `app.graph.neo4j_client` | `5d05e6f5` deleted old path | `app.graph.knowledge.client` | migrate | collect `Neo4jClient` deletion behavior |
| `tests/test_react_agent.py` | `app.agents.react_agent` | `d1075732` deleted wrapper | `app.agents.tool.react` | migrate | collect ReAct tool tests |
| `tests/test_streaming_analytics_logging.py` | `app.graph.streaming.safe_wrappers` | `5d05e6f5` removed wrappers | `app.api.query.streaming.execution`, retrieval logger | migrate | collect analytics at current streaming boundary |
| `tests/test_streaming_react_agent_class.py` | `app.graph.streaming.stream_processor` | `5d05e6f5` removed processor | `app.api.query.streaming.execution`, `app.agents.tool.react` | migrate | collect streaming agent-class propagation |
| `tests/test_weight_optimization.py` | `app.agents.quality_orchestrator_agent` | `d1075732` deleted wrapper | `app.agents.validation.quality_orchestrator` | migrate | collect quality weighting tests |
| `tests/test_workflow_fixes.py` | `app.graph.workflow` | `5d05e6f5` removed LangGraph workflow; `ccbaec34` removed last legacy workflow test | none; supported orchestration is not that public API | delete-retired-contract | confirm each assertion is only a removed workflow helper contract |
| `tests/unit/test_chinese_document_indexer.py` | `jieba` | declared in `pyproject.toml`; absent in probe | `app.services.language.chinese_document_indexer` | install-dependency | install sync, then collect indexer tests |
| `tests/unit/test_chinese_query_preprocessor.py` | `jieba` | declared in `pyproject.toml`; absent in probe | `app.services.language.chinese_query_preprocessor` | install-dependency | install sync, then collect preprocessor tests |
| `tests/unit/test_chinese_tokenizer.py` | `jieba` | declared in `pyproject.toml`; absent in probe | `app.services.language.chinese_tokenizer` | install-dependency | install sync, then collect tokenizer tests |
| `tests/unit/test_synthesis_language.py` | `app.agents.synthesis_agent` | `d1075732` deleted wrapper | `app.agents.synthesizer.generation` | migrated | canonical lookup patches pass |
| `tests/unit/test_unified_agents.py` | `base_agent`, `unified_config`, `shared_utils` wrappers | `d1075732`/`54192131` deleted wrappers | `app.agents.shared.base`, `config`, `utils`, `result_schemas`; `app.agents.rag.vector` | migrated | 24 current shared/vector contract tests pass |
| `tests/unit/test_web_research_agent.py` | `app.agents.web_research_agent` | `d1075732` deleted wrapper | `app.agents.rag.web`, `app.agents.rag.web_utils` | migrate | collect web-research utility tests |

## Matrix review

The matrix contains exactly 47 data rows. Each brief-listed path appears once. Every owner above was verified as a current backend module (and, where stated, by a current caller); every retirement conclusion cites an explicit removal commit rather than file absence alone. The only live legacy-path scan prescribed by the task returned no results.
