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

## 47-file matrix

| test file | missing import/dependency | retirement evidence | current owner | action | focused verification |
| --- | --- | --- | --- | --- | --- |
| `tests/agents/test_answer_validator.py` | `app.agents.answer_validator_agent` | `d1075732` deleted wrapper | `app.agents.validation.public` | migrate | collect this file after remapping public validation exports |
| `tests/agents/test_answer_validator_cascade.py` | `app.agents.validation_cascade` | `54192131` deleted wrapper | `app.agents.validation.cascade` | migrate | collect this file against `ValidationCascade` |
| `tests/agents/test_context_tracker.py` | `app.agents.context_tracker_agent` | `d1075732` deleted wrapper | `app.services.sessions.context_tracker` | migrate | collect this file against session context owner |
| `tests/agents/test_fact_verification.py` | `app.agents.fact_verification` | `54192131` deleted wrapper | `app.agents.validation.fact_verification` | migrate | collect fact-verification tests |
| `tests/agents/test_hallucination_detection.py` | `app.agents.hallucination_patterns` | `54192131` deleted wrapper | `app.agents.validation.hallucination_patterns` | migrate | collect pattern tests |
| `tests/agents/test_quality_orchestrator.py` | `app.agents.quality_orchestrator_agent` | `d1075732` deleted wrapper | `app.agents.validation.quality_orchestrator` | migrate | collect orchestrator tests |
| `tests/agents/test_react_agent_tools.py` | `app.agents.react_agent` | `d1075732` deleted wrapper | `app.agents.tool.react` | migrate | collect tool-react tests |
| `tests/agents/test_relevance_scoring.py` | `app.agents.relevance_scoring` | `54192131` deleted wrapper | `app.agents.rag.relevance` | migrate | collect relevance tests |
| `tests/agents/test_retrieval_quality.py` | `app.agents.retrieval_quality_agent` | `d1075732` deleted wrapper | `app.agents.rag.retrieval_quality` | migrate | collect retrieval-quality tests |
| `tests/agents/test_route_accuracy.py` | `app.agents.route_accuracy_tracker` | `54192131` deleted wrapper | `app.agents.router.accuracy`, `app.domain.contracts` | migrate | collect route-accuracy tests with current decision contract |
| `tests/agents/test_route_validator.py` | `app.agents.route_validator_agent` | `d1075732` deleted wrapper | `app.agents.router.validator` | migrate | collect route-validator tests |
| `tests/agents/test_router_accuracy.py` | `app.agents.router_agent` | `d1075732` deleted wrapper | `app.agents.router.routing` | migrate | collect routing samples against `decide_route` |
| `tests/agents/test_router_calibration.py` | `app.agents.router_calibration` | `54192131` deleted wrapper | `app.agents.router.calibration` | migrate | collect calibrator tests |
| `tests/agents/test_router_calibration_integration.py` | `app.agents.router_agent` | `d1075732` deleted wrapper | `app.agents.router.routing`, `app.agents.router.calibration` | migrate | collect router/calibrator integration |
| `tests/agents/test_router_enhanced.py` | `app.agents.router_examples` | `54192131` deleted wrapper | `app.agents.router.examples` | migrate | collect few-shot example tests |
| `tests/agents/test_router_fallback.py` | `app.agents.router_agent` | `d1075732`, `54192131`, and `e322be7e` removed compatibility contract; the later `agent_config` import is migration analysis, not this collection failure | none; typed router owns supported routing | delete-retired-contract | confirm no supported replacement of legacy fallback/config API |
| `tests/agents/test_synthesis_citation.py` | `app.agents.synthesis_agent` | `d1075732` deleted wrapper | `app.agents.synthesizer.generation`, `templates` | migrate | collect citation tests against typed synthesizer |
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
| `tests/unit/test_synthesis_language.py` | `app.agents.synthesis_agent` | `d1075732` deleted wrapper | `app.agents.synthesizer.generation` | migrate | collect language synthesis tests |
| `tests/unit/test_unified_agents.py` | `base_agent`, `unified_config`, `shared_utils` wrappers | `d1075732`/`54192131` deleted wrappers | `app.agents.shared.base`, `config`, `utils`, `result_schemas` | migrate | collect shared-agent contract tests |
| `tests/unit/test_web_research_agent.py` | `app.agents.web_research_agent` | `d1075732` deleted wrapper | `app.agents.rag.web`, `app.agents.rag.web_utils` | migrate | collect web-research utility tests |

## Matrix review

The matrix contains exactly 47 data rows. Each brief-listed path appears once. Every owner above was verified as a current backend module (and, where stated, by a current caller); every retirement conclusion cites an explicit removal commit rather than file absence alone. The only live legacy-path scan prescribed by the task returned no results.
