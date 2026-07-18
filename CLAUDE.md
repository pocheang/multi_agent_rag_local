# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

**Conda Environment**: `rag-local` (Python 3.11+)

All operations must use this conda environment:
```bash
conda activate rag-local
```

## Common Commands

### Backend

**Start Development Server**
```bash
uvicorn app.api.main:app --reload --port 8000
# Alternative entry point:
uvicorn app.main:app --reload --port 8000
```

**Run Tests**
```bash
pytest tests/ -v                    # All tests
pytest tests/agents/ -v             # Agent tests only
pytest --cov=app tests/             # With coverage
pytest -m unit                      # Unit tests only
pytest -m integration               # Integration tests only
```

**Linting and Formatting**
```bash
ruff check .                        # Lint check
ruff format .                       # Format code
```

**Database Initialization**
```bash
python scripts/init_db.py
```

### Frontend

**Start Development Server**
```bash
cd frontend
npm install                         # First time only
npm run dev                         # Starts Vite dev server (port 5173)
```

**Build for Production**
```bash
cd frontend
npm run build                       # TypeScript compile + Vite build
npm run preview                     # Preview production build
```

## Architecture Overview

### Multi-Agent System

This is a **production-grade RAG system** with 11 specialized agents orchestrated by LangGraph. Key architectural pattern: **specialized agents collaborate** rather than one monolithic agent.

#### Agent Layers (4-tier architecture)

**Layer 1: Routing (2 agents)**
- `EnhancedRouterAgent` ([app/agents/enhanced_router_agent.py](app/agents/enhanced_router_agent.py)): Query intent classification with few-shot learning (6 examples in `router_examples.py`)
- `RouteValidatorAgent` ([app/agents/route_validator_agent.py](app/agents/route_validator_agent.py)): Validates routing decisions

**Layer 2: Retrieval (4 agents)**
- `EnhancedVectorRAGAgent` ([app/agents/enhanced_vector_rag_agent.py](app/agents/enhanced_vector_rag_agent.py)): Hybrid retrieval (vector + BM25 + reranking)
- `GraphRAGAgent` ([app/agents/graph_rag_agent_enhanced.py](app/agents/graph_rag_agent_enhanced.py)): Neo4j knowledge graph queries
- `ReactAgent` ([app/agents/react_agent.py](app/agents/react_agent.py)): Multi-hop reasoning with tool calls
- `WebResearchAgent` ([app/agents/web_research_agent.py](app/agents/web_research_agent.py)): Web fallback when local knowledge insufficient

**Layer 3: Quality Assurance (3 agents)**
- `RetrievalQualityAgent` ([app/agents/retrieval_quality_agent.py](app/agents/retrieval_quality_agent.py)): LLM-based relevance scoring
- `AnswerValidatorAgent` ([app/agents/answer_validator_agent.py](app/agents/answer_validator_agent.py)): 4-layer validation cascade (rules → NLI → citations → deep LLM)
- `ContextTrackerAgent` ([app/agents/context_tracker_agent.py](app/agents/context_tracker_agent.py)): Multi-turn conversation context

**Layer 4: Orchestration (2 agents)**
- `QualityOrchestratorAgent` ([app/agents/quality_orchestrator_agent.py](app/agents/quality_orchestrator_agent.py)): 5-dimension quality score fusion
- `SynthesisAgent` ([app/agents/synthesis_agent.py](app/agents/synthesis_agent.py)): Citation-first answer generation

### LangGraph State Machine

The workflow is defined as a directed acyclic graph (DAG) in [app/graph/nodes/](app/graph/nodes/):

**Execution Flow:**
1. `router_node` → Routes query to vector/graph/web/react
2. `entry_decider_node` → Conditional routing based on confidence
3. Execution nodes (vector/graph/web/react) → Retrieve information
4. `vector_decider_node` → Quality gate (retry if quality < threshold)
5. `adaptive_planner_node` → Decides if reasoning needed
6. `react_node` → Optional multi-hop reasoning
7. `synthesis_node` → Generate answer with citations
8. `graph_decider_node` → 4-layer answer validation
9. Quality report generation → Final output

**Key Pattern**: All nodes share a `StateGraph` object containing `query`, `route_decision`, `retrieval_results`, `answer`, `citations`, `validation_result`, `quality_report`, etc. This enables stateful workflow execution with conditional routing.

### Quality Assurance System

**5-Layer Defense** (implemented in `enhanced_rag_workflow.py`):
1. **Route validation**: Confidence threshold (>0.6), consistency checks
2. **Retrieval quality**: Batch relevance scoring via Claude Haiku
3. **Answer validation**: 4-layer cascade (L1: rules, L2: NLI model, L3: citation check, L4: deep LLM)
4. **Score fusion**: Weighted combination (route 10% + retrieval 30% + factual 45% + quality 10% + citation 5%)
5. **Context tracking**: Multi-turn coherence validation

**Citation-First Principle**: Every factual claim must have inline citation `[doc_id:page]` during generation, not retrofitted afterward. Enforced by `synthesis_agent.py` and `synthesis_templates.py`.

**Hallucination Detection**: Pattern-based checks in `hallucination_patterns.py` (date/number/entity/negation hallucinations).

### Retrieval Strategy

**Hybrid Retrieval** ([app/retrievers/hybrid_retriever.py](app/retrievers/hybrid_retriever.py)):
- **Vector search**: Sentence-Transformers BGE-M3 embeddings → ChromaDB
- **BM25 search**: Jieba tokenization → Rank-BM25
- **Fusion**: Reciprocal Rank Fusion (RRF)
- **Reranking**: BGE-Reranker-V2-M3 (top 5 results)

**Dynamic Top-K** (in `vector_rag_agent.py`):
- Simple queries: top_k=15
- Medium queries: top_k=20
- Complex queries: top_k=30

### Configuration System

Key config files in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds
- `retrieval_config.json`: Top-K, similarity thresholds, reranking settings
- `fact_verification.json`: NLI thresholds, hallucination patterns
- `retry_policy.json`: Retry strategies, circuit breaker settings

Runtime config: [app/core/config.py](app/core/config.py) loads from `.env` and config files.

### Technology Stack

**Backend**: FastAPI + LangGraph + LangChain
**Vector Store**: ChromaDB (local, persistent)
**Graph Store**: Neo4j (optional)
**Database**: PostgreSQL (user/session management)
**Frontend**: React 18 + TypeScript + Vite + Ant Design
**Models**: OpenAI GPT-4 (primary), Claude Haiku (batch scoring), Sentence-Transformers (embeddings)

## Development Patterns

### Adding a New Agent

1. Create agent file in `app/agents/` inheriting base patterns from existing agents
2. Implement core methods: `process()` or `run()`
3. Add to workflow in `app/agents/enhanced_rag_workflow.py`
4. Create corresponding LangGraph node in `app/graph/nodes/` if needed
5. Add tests in `tests/agents/test_<agent_name>.py`

### LangGraph Node Structure

All nodes in `app/graph/nodes/` follow this pattern:
```python
from langgraph.graph import StateGraph
from typing import TypedDict

class GraphState(TypedDict):
    query: str
    # ... other state fields

def my_node(state: GraphState) -> GraphState:
    # Process state
    return updated_state

# Add to graph
graph.add_node("my_node", my_node)
graph.add_edge("previous_node", "my_node")
```

### Quality Metrics

Track these metrics when modifying agents:
- **Router accuracy**: >99% (v0.6.0 baseline)
- **Hallucination rate**: <10% (v0.6.0 baseline)
- **Citation completeness**: >96% (v0.6.0 baseline)
- **Precision@5**: >0.90
- **P95 latency**: <4 seconds

Use `scripts/eval_retrieval.py` and `scripts/benchmark_pipeline.py` for evaluation.

### Testing Strategy

- **Unit tests** (`-m unit`): Individual agent/service logic
- **Integration tests** (`-m integration`): End-to-end workflow tests
- **Performance tests** (`-m performance`): Latency and throughput benchmarks

Mock external LLM calls in unit tests. Use `pytest-asyncio` for async tests.

## Important Notes

- **Conda environment is mandatory**: Dependencies assume conda-managed packages
- **Do not commit** files in `.gitignore`: `internal_docs/`, `.env`, `data/chroma/`, logs
- **SSE streaming**: Real-time status updates use Server-Sent Events (see `app/api/routes/enhanced_query.py`)
- **Retry logic**: Max 2 retries per stage (routing/retrieval/synthesis) with exponential backoff
- **Circuit breaker**: Opens after 5 consecutive failures, closes after 60s cooldown
- **Language detection**: Auto-detected via `language_analytics.py`, affects answer language (100% Chinese or 100% English, no mixing)

## Common Issues

**"ModuleNotFoundError"**: Verify conda environment is activated
**"ChromaDB not found"**: Run `python scripts/init_db.py` to initialize vector store
**"Neo4j connection failed"**: Neo4j is optional; system falls back to vector-only retrieval
**Frontend CORS errors**: Ensure backend is running on port 8000
