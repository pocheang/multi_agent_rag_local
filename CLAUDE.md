# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Agent Local RAG system (v0.3.0) - A production-grade retrieval-augmented generation platform with FastAPI backend, React frontend, and Neo4j graph database integration.

**Recent Changes (v0.3.0)**: Major refactoring completed - codebase modularized from 7 large files (9135 lines) into 65 focused modules (846 lines in main files), reducing code by 90.7% while maintaining 100% backward compatibility.

**Core Architecture:**
- **Backend**: FastAPI with LangGraph-based multi-agent workflow orchestration
- **Frontend**: React + Vite + TypeScript
- **Retrieval**: Hybrid system combining vector search (ChromaDB), BM25, and reranking
- **Graph**: Neo4j for knowledge graph extraction and traversal
- **LLM Backends**: Supports OpenAI (default: gpt-5.4-codex), Anthropic Claude, and Ollama
- **Tiered Execution**: Query complexity classification with latency budget enforcement (fast/balanced/deep tiers)

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

The system uses LangGraph to orchestrate a multi-agent workflow. Main entry point: `app/graph/workflow.py`

**Workflow Modules** (`app/graph/`):
- `workflow.py` - Main workflow builder and runner (99 lines)
- `state.py` - GraphState type definition
- `nodes/` - Individual workflow nodes:
  - `router_node.py` - Routing decision
  - `adaptive_planner_node.py` - Adaptive planning
  - `vector_node.py` - Vector retrieval
  - `graph_node.py` - Graph retrieval
  - `web_node.py` - Web search
  - `synthesis_node.py` - Answer synthesis
  - `decider_nodes.py` - Decision logic
  - `safe_wrappers.py` - Resilience wrappers
- `routing/` - Routing logic:
  - `route_logic.py` - Route decision functions

**Agent Implementations**:
1. **Router Agent** (`app/agents/router_agent.py`) - Decides routing strategy
2. **Vector RAG Agent** (`app/agents/vector_rag_agent.py`) - Hybrid retrieval
3. **Graph RAG Agent** (`app/agents/graph_rag_agent.py`) - Neo4j queries
4. **Web Research Agent** (`app/agents/web_research_agent.py`) - Web search
5. **Synthesis Agent** (`app/agents/synthesis_agent.py`) - Answer synthesis

**State Flow**: `GraphState` (from `app/graph/state.py`) passes through agents.

### Hybrid Retrieval System

Main entry point: `app/retrievers/hybrid_retriever.py` (109 lines)

**Retrieval Modules** (`app/retrievers/hybrid/`):
- `strategy.py` - Retrieval strategy flags (baseline/safe/advanced)
- `fusion.py` - RRF (Reciprocal Rank Fusion) algorithm
- `adaptive_params.py` - Dynamic parameter adjustment based on query complexity
- `rank_features.py` - Ranking feature computation
- `caching.py` - Redis + memory dual-layer caching
- `candidate_collection.py` - Candidate collection and fusion logic
- `parent_expansion.py` - Parent-child context expansion

**Features**:
- **Vector Search**: ChromaDB with configurable similarity thresholds
- **BM25**: Keyword-based retrieval from corpus store
- **RRF Fusion**: Combines vector and BM25 results
- **Reranking**: BAAI/bge-reranker-v2-m3 for final ranking
- **Parent-Child Chunking**: Small chunks for retrieval, large parent chunks for context
- **Dynamic Retrieval**: Adjusts top_k based on query complexity
- **Retrieval Caching**: TTL-based cache (memory or Redis)
- **Tier-Aware Execution**: Budget enforcement per tier (fast: 5/3, balanced: 10/5, deep: 20/10)

### Tiered Execution System (v0.2.4)

The system implements intelligent query routing with latency budget enforcement:

**Tier Classification** (`app/services/tier_classifier.py` - planned):
- **Fast Tier**: Simple factual queries, single-entity lookup, high doc hit likelihood (>0.8), query length <50 tokens
- **Balanced Tier**: Default for most queries, moderate complexity
- **Deep Tier**: Multi-hop reasoning, low doc hit likelihood (<0.3), explicit comprehensive answer requests

**Latency Budget Manager** (`app/services/budget_policy.py` - planned):
- **Fast**: retrieval_top_k=5, rerank_top_k=3, max_retrieval_time=800ms, max_synthesis_tokens=300, web_fallback=disabled
- **Balanced**: retrieval_top_k=10, rerank_top_k=5, max_retrieval_time=2000ms, max_synthesis_tokens=800, web_fallback=conditional
- **Deep**: retrieval_top_k=20, rerank_top_k=10, max_retrieval_time=5000ms, max_synthesis_tokens=1500, web_fallback=enabled

**Load-Based Degradation**:
- System load >80%: Automatic tier downgrade by one level
- System load >95%: Force all queries to fast tier

**UX Telemetry**:
- First token latency tracking (P50 ≤ 2s, P95 ≤ 4s targets)
- Tier distribution monitoring (fast/balanced/deep percentages)
- Tier confidence scoring and misclassification detection
- Citation coverage per tier
- Re-ask rate tracking (query similarity >0.7 within 5min window)

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

- **Auth Service** (`app/services/auth/`) - Modularized authentication system:
  - `auth_service.py` - Main service coordination
  - `user_manager.py` - User CRUD operations
  - `session_manager.py` - Session management
  - `audit_logger.py` - Hash-chained audit trail
  - `password_utils.py` - Password hashing/verification
  - `encryption.py` - API key encryption
  - `validation.py` - Input validation
- **Backward Compatibility**: `app/services/auth_db.py` imports from `app/services/auth/`
- **RBAC** (`app/services/rbac.py`) - Permission checking with `can(user, action, resource)`
- **User Classifications**: admin, power_user, standard_user, guest

### Configuration System

Settings loaded from `.env` via Pydantic (`app/core/config.py`):

- **Model Backends**: Switch between OpenAI, Anthropic Claude, and Ollama via `MODEL_BACKEND`
- **Retrieval Profiles**: `baseline`, `advanced`, `safe` - control retrieval aggressiveness
- **Feature Flags**: Enable/disable query rewriting, decomposition, dynamic retrieval, etc.
- **Observability**: OpenTelemetry tracing, Prometheus metrics at `/metrics`

### API Structure

Main API in `app/api/main.py` (140 lines) - Modularized into route modules:

**Route Modules** (`app/api/routes/`):
- `query.py` - Query endpoints (streaming and sync)
- `sessions.py` - Session CRUD operations
- `documents.py` - Document upload and indexing
- `prompts.py` - Prompt template management
- `memory.py` - Memory management
- `auth.py` - Authentication endpoints
- `admin_users.py` - User management (admin)
- `admin_ops.py` - Operational tools (admin)
- `admin_settings.py` - System settings (admin)
- `health.py` - Health checks and metrics

**Shared Dependencies** (`app/api/dependencies.py`, 411 lines):
- Authentication dependencies
- Database session management
- Request context setup
- Common validators

**Key Endpoints**:
- **Query**: `/query` (streaming), `/query-sync` (non-streaming)
- **Sessions**: `/sessions/*` - CRUD for chat sessions
- **Documents**: `/upload`, `/index/*` - File upload and indexing
- **Admin Ops**: `/admin/ops/*` - Retrieval profiles, canary testing, benchmarking
- **Auth**: `/auth/login`, `/auth/logout`, `/auth/me`
- **Health**: `/health`, `/ready`, `/metrics`

### Data Ingestion

Main entry point: `app/ingestion/loaders.py` (70 lines)

**Loader Modules** (`app/ingestion/loaders/`):
- `pdf_loader.py` - PDF text extraction and image OCR
- `image_loader.py` - Image file loading
- `text_loader.py` - Text file loading with encoding fallback

**Utility Modules** (`app/ingestion/utils/`):
- `ocr_utils.py` - OCR processing with Tesseract (preprocessing, auto-rotation, multi-PSM)
- `vision_utils.py` - Vision API integration (OpenAI/Ollama) for image captioning
- `people_detection.py` - Face and person detection using OpenCV

**Supported Formats**:
- PDF: Text extraction + embedded image OCR
- Images: PNG, JPG, JPEG, BMP, TIF, TIFF, WEBP, GIF
- Text: TXT, MD, CSV, LOG, JSON, YAML, YML, TOML, INI

### Streaming Query Processing

Main entry point: `app/graph/streaming.py` (10 lines)

**Streaming Modules** (`app/graph/streaming/`):
- `stream_processor.py` - Core streaming logic with real-time events
- `safe_wrappers.py` - Resilient agent wrappers (bulkhead, circuit breaker, retry)
- `sse_encoder.py` - Server-Sent Events encoding

**Features**:
- Real-time event streaming (routing, retrieval, synthesis)
- Parallel hybrid execution (vector + graph)
- Graceful degradation on failures
- Answer grounding and safety checks

## Key Design Patterns

1. **Adaptive RAG**: System adjusts retrieval strategy based on query complexity and available evidence
2. **Tiered Execution**: Query complexity classification with hard latency budgets (fast/balanced/deep)
3. **Evidence Grounding**: Answers are grounded with citations and conflict detection
4. **Safety Scanning**: Answer safety checks before returning to user
5. **Explainability**: Each response includes reasoning trace and retrieval metadata
6. **Source Allowlisting**: Users can restrict retrieval to specific document sources
7. **Consistency Guard**: Detects and flags inconsistent responses across retries
8. **Load-Based Degradation**: Automatic tier downgrade under high system load (>80%)

## Testing Strategy

Tests in `tests/` directory:

- **Unit Tests**: Individual service/component testing
- **Integration Tests**: End-to-end workflow testing
- **Concurrency Tests**: `test_concurrency_regression.py` - Race condition detection
- **Resilience Tests**: `test_agent_resilience.py` - Chaos and failure injection
- **Admin Tests**: `test_admin_ops_api.py`, `test_admin_user_provisioning.py`

## Important Notes

- **Neo4j Required**: Backend will not start without Neo4j connection
- **Model Backend**: Default is Anthropic Claude (requires `ANTHROPIC_API_KEY`). Set `MODEL_BACKEND=openai` for OpenAI or `MODEL_BACKEND=ollama` for local models
- **Data Directories**: `data/docs` (source documents), `data/chroma` (vector store), `data/sessions` (chat history)
- **Chunk Stores**: `data/chunks/chunks.jsonl` (child chunks), `data/chunks/parents.jsonl` (parent chunks)
- **Auto-Ingestion**: When enabled, watches `data/docs` and `data/uploads` for new files
- **Streaming**: All query responses support SSE streaming via `/query` endpoint
- **CORS**: Configured for frontend at `http://127.0.0.1:5173`
