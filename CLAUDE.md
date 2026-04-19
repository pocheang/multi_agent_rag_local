# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Agent Local RAG system (v0.2.2.1) - A production-grade retrieval-augmented generation platform with FastAPI backend, React frontend, and Neo4j graph database integration.

**Core Architecture:**
- **Backend**: FastAPI with LangGraph-based multi-agent workflow orchestration
- **Frontend**: React + Vite + TypeScript
- **Retrieval**: Hybrid system combining vector search (ChromaDB), BM25, and reranking
- **Graph**: Neo4j for knowledge graph extraction and traversal
- **LLM Backends**: Supports both OpenAI (default: gpt-5.4-codex) and Ollama

## Development Commands

### Backend Setup & Running

```bash
# Initial setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
cp .env.example .env

# Start Neo4j (required)
docker compose up -d neo4j

# Run backend server
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev  # Starts on http://127.0.0.1:5173/app
npm run build  # Production build
npm run preview  # Preview production build
npm run lint  # Lint TypeScript/React code
```

### Testing

```bash
# Run all tests
pytest -q

# Run specific test file
pytest tests/test_<name>.py -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run CI quality gate checks (pre-release validation)
python scripts/ci_quality_gate.py
```

### Data Ingestion

```bash
# Ingest documents from data/docs directory
python scripts/ingest.py

# The system also supports auto-ingestion via AUTO_INGEST_ENABLED=true in .env
```

### Operational Scripts

Located in `scripts/`:
- `chaos_probe.py` - Chaos engineering probes for resilience testing
- `load_test_query.py` - Load testing for query endpoints
- `benchmark_pipeline.py` - Benchmark retrieval pipeline performance
- `eval_retrieval.py` - Evaluate retrieval quality
- `ci_quality_gate.py` - CI quality gate checks
- `apply_rollback_profile.py` - Apply rollback retrieval profiles
- `migrate_*.py` - Data migration scripts

## Architecture Deep Dive

### Multi-Agent Workflow (LangGraph)

The system uses LangGraph to orchestrate a multi-agent workflow defined in `app/graph/workflow.py`:

1. **Router Agent** (`app/agents/router_agent.py`) - Decides routing strategy based on query intent
2. **Vector RAG Agent** (`app/agents/vector_rag_agent.py`) - Performs hybrid retrieval (vector + BM25 + reranking)
3. **Graph RAG Agent** (`app/agents/graph_rag_agent.py`) - Queries Neo4j knowledge graph
4. **Web Research Agent** (`app/agents/web_research_agent.py`) - Performs web search when local knowledge insufficient
5. **Synthesis Agent** (`app/agents/synthesis_agent.py`) - Synthesizes final answer with grounding and safety checks

**State Flow**: `GraphState` (TypedDict) passes through agents, accumulating results and metadata.

### Hybrid Retrieval System

Located in `app/retrievers/hybrid_retriever.py`:

- **Vector Search**: ChromaDB with configurable similarity thresholds
- **BM25**: Keyword-based retrieval from corpus store
- **RRF Fusion**: Reciprocal Rank Fusion combines vector and BM25 results
- **Reranking**: BAAI/bge-reranker-v2-m3 for final ranking
- **Parent-Child Chunking**: Small chunks for retrieval, large parent chunks for context
- **Dynamic Retrieval**: Adjusts top_k based on query complexity
- **Retrieval Caching**: TTL-based cache (memory or Redis) for repeated queries

### Runtime Resilience Modules

The system includes production-grade resilience patterns in `app/services/`:

- **Bulkhead Isolation** (`bulkhead.py`) - Resource isolation per component
- **Circuit Breaker** (`resilience.py`) - Fail-fast for degraded services
- **Query Guard** (`query_guard.py`) - Rate limiting and overload protection
- **Quota Guard** (`quota_guard.py`) - Per-user quota enforcement
- **Background Queue** (`background_queue.py`) - Async task processing
- **Alerting** (`alerting.py`) - Webhook-based alert emission
- **Query Result Cache** (`query_result_cache.py`) - Response caching layer
- **Hybrid Executor** (`hybrid_executor.py`) - Adaptive execution strategy

### Authentication & Authorization

- **Auth Service** (`app/services/auth_db.py`) - User management, role-based access control (RBAC)
- **RBAC** (`app/services/rbac.py`) - Permission checking with `can(user, action, resource)`
- **Session Management** - Token-based auth with configurable TTL
- **User Classifications**: admin, power_user, standard_user, guest
- **Audit Logging**: Hash-chained audit trail for compliance

### Configuration System

Settings loaded from `.env` via Pydantic (`app/core/config.py`):

- **Model Backends**: Switch between OpenAI and Ollama via `MODEL_BACKEND`
- **Retrieval Profiles**: `baseline`, `advanced`, `safe` - control retrieval aggressiveness
- **Feature Flags**: Enable/disable query rewriting, decomposition, dynamic retrieval, etc.
- **Observability**: OpenTelemetry tracing, Prometheus metrics at `/metrics`

### API Structure

Main API in `app/api/main.py`:

- **Query Endpoints**: `/query` (streaming), `/query-sync` (non-streaming)
- **Session Management**: `/sessions/*` - CRUD for chat sessions
- **Document Management**: `/upload`, `/index/*` - File upload and indexing
- **Admin Ops**: `/admin/ops/*` - Retrieval profiles, canary testing, A/B comparison, benchmarking
- **Auth Endpoints**: `/auth/login`, `/auth/logout`, `/auth/me`
- **Health Checks**: `/health`, `/ready`, `/metrics`

### Frontend Architecture

React SPA in `frontend/src/`:

- **Pages**: `ChatPage.tsx` (main chat interface), `LoginPage.tsx`, `AdminPage.tsx`
- **API Client**: `lib/api.ts` - Centralized API calls with auth token handling
- **Routing**: React Router for navigation
- **Streaming**: Server-Sent Events (SSE) for real-time response streaming

## Key Design Patterns

1. **Adaptive RAG**: System adjusts retrieval strategy based on query complexity and available evidence
2. **Evidence Grounding**: Answers are grounded with citations and conflict detection
3. **Safety Scanning**: Answer safety checks before returning to user
4. **Explainability**: Each response includes reasoning trace and retrieval metadata
5. **Source Allowlisting**: Users can restrict retrieval to specific document sources
6. **Consistency Guard**: Detects and flags inconsistent responses across retries

## Testing Strategy

Tests in `tests/` directory:

- **Unit Tests**: Individual service/component testing
- **Integration Tests**: End-to-end workflow testing
- **Concurrency Tests**: `test_concurrency_regression.py` - Race condition detection
- **Resilience Tests**: `test_agent_resilience.py` - Chaos and failure injection
- **Admin Tests**: `test_admin_ops_api.py`, `test_admin_user_provisioning.py`

## Important Notes

- **Neo4j Required**: Backend will not start without Neo4j connection
- **Model Backend**: Default is OpenAI (requires `OPENAI_API_KEY`). Set `MODEL_BACKEND=ollama` for local models
- **Data Directories**: `data/docs` (source documents), `data/chroma` (vector store), `data/sessions` (chat history)
- **Chunk Stores**: `data/chunks/chunks.jsonl` (child chunks), `data/chunks/parents.jsonl` (parent chunks)
- **Auto-Ingestion**: When enabled, watches `data/docs` and `data/uploads` for new files
- **Streaming**: All query responses support SSE streaming via `/query` endpoint
- **CORS**: Configured for frontend at `http://127.0.0.1:5173`
