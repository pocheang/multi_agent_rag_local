# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

**Conda Environment**: `rag-local` (Python 3.11+)

All operations must use this conda environment:
```bash
conda activate rag-local
```

## Project Information

**Name**: QueryMind（智询）  
**Version**: 0.6.2.1  
**Language Support**: Bilingual (Chinese/English) via i18next  
**License**: MIT

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
npm run preview                     # Preview production build (port 4173)
```

**Testing**
```bash
cd frontend
npm run test                        # Run Vitest tests
```

### Docker Deployment

```bash
export OPENAI_API_KEY="your-api-key"
./deploy/scripts/deploy.sh production balanced
```

Configuration lives in `config/` and runtime files in `.runtime/`.

## Architecture Overview

### Pragmatic RAG System in Transition

This is a **working RAG system** built on proven components (LangChain, ChromaDB, FastAPI). The system evolved from a multi-agent LangGraph architecture and is currently in a **transition state** - core functionality is stable, but the architecture is being incrementally modernized.

**Current architecture**: Legacy retrieval and synthesis components wrapped with adapter services for cleaner interfaces. The `RAGPipeline` provides the public API, while `OrchestrationEngine` coordinates execution flow.

**What works well**: Retrieval quality, answer synthesis, bilingual support, session management.

**What's being improved**: Service boundaries, configuration management, error handling consistency.

### Core Components

The system has **3 primary components** and **3 optional components**:

**Primary (always active)**:
1. **Router** ([app/agents/router/service.py](app/agents/router/service.py))
   - Query intent classification and route selection
   
2. **Retriever** ([app/agents/rag/service.py](app/agents/rag/service.py))
   - Hybrid search: vector (ChromaDB) + BM25 + reranking
   - Optional: Knowledge graph (Neo4j), web search
   
3. **Synthesizer** ([app/agents/synthesizer/service.py](app/agents/synthesizer/service.py))
   - Citation-first answer generation from evidence

**Optional (route-dependent)**:
4. **Planner** - Task decomposition for complex queries
5. **Tool Runner** - Multi-hop reasoning (ReAct pattern)
6. **Finalizer** - Quality validation and safety checks

### Pipeline Profiles

Three execution profiles are supported:

- **standard**: Balanced quality and performance
- **strict_quality**: Maximum validation, slower
- **advanced**: Includes multi-hop reasoning and web research

### Execution Flow

```
Request → RAGPipeline.execute()
   ↓
OrchestrationEngine
   ↓
1. Router → determines query type and route
2. Planner → (optional) decomposes complex queries
3. Retriever → gathers evidence from vector/BM25/graph/web
4. Tool Runner → (optional) executes tools for react route
5. Synthesizer → generates answer with inline citations
6. Finalizer → (optional) validates quality and safety
   ↓
PipelineResult → returned to caller
```

**Note**: Steps 2, 4, 6 are conditionally executed based on route and profile settings. The flow is sequential with concurrent retrieval from multiple sources in step 3.

### Quality Assurance

**Validation layers** (applied based on profile):
1. **Route confidence checks**: Threshold-based validation
2. **Retrieval quality scoring**: Batch relevance checks via Claude Haiku
3. **Answer validation**: Citation completeness, hallucination detection, NLI checks
4. **Safety checks**: Content filtering, bias detection

**Citation-First Principle**: Factual claims must include inline citations `[doc_id:page]` during generation.

**Note**: Quality validation can be adjusted via profile settings. The `standard` profile balances quality and speed; `strict_quality` enables all validation layers.

### Retrieval Strategy

**Hybrid Retrieval** ([app/retrievers/hybrid_retriever.py](app/retrievers/hybrid_retriever.py)):
- **Vector search**: Sentence-Transformers BGE-M3 embeddings → ChromaDB
- **BM25 search**: Jieba tokenization → Rank-BM25
- **Fusion**: Reciprocal Rank Fusion (RRF)
- **Reranking**: BGE-Reranker-V2-M3 (top 5 results)
- **Dynamic Top-K**: Query complexity determines retrieval depth (15-30 results)

### Configuration System

**Essential config files** in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds
- `retrieval_config.json`: Top-K settings, similarity thresholds
- `fact_verification.json`: NLI thresholds, hallucination patterns

**Runtime config**: [app/core/config.py](app/core/config.py) loads from `.env`

**Additional config**: [app/agents/shared/config.py](app/agents/shared/config.py) contains component-specific settings (currently undergoing simplification - many constants are legacy tuning parameters that will be consolidated or removed)

### Technology Stack

**Backend**: FastAPI + LangChain
**Vector Store**: ChromaDB (local, persistent)
**Graph Store**: Neo4j (optional)
**Database**: PostgreSQL (user/session management)
**Frontend**: React 18 + TypeScript + Vite + Zustand (state) + i18next (i18n)
**Models**: OpenAI GPT-4 (primary), Claude Haiku (batch scoring), Sentence-Transformers (embeddings)
**Deployment**: Docker Compose with deployment scripts in `deploy/scripts/`

## Development Patterns

### Working with the Current Architecture

**Understanding the codebase**:
- Services in `app/agents/*Service` are **adapter wrappers** around existing implementations
- The actual logic is in modules like `app/agents/router/routing.py`, `app/agents/synthesizer/generation.py`
- Services provide cleaner interfaces but delegate to these legacy components

**When modifying functionality**:
1. **For interface changes**: Modify the `*Service` class in `service.py`
2. **For logic changes**: Modify the underlying implementation modules
3. **For new features**: Decide if it belongs in the adapter or the implementation

**Architecture guidelines**:
- Keep services stateless
- Use typed contracts (`RouteDecision`, `EvidenceBundle`, `FinalAnswer`) for communication
- Avoid adding more configuration constants unless absolutely necessary
- Consider if logic should be algorithmic vs. configuration-driven

### Quality Metrics

Monitor these when modifying retrieval or synthesis:
- **Router accuracy**: Target >95% on test queries
- **Citation completeness**: Target >90% (answers with evidence should cite it)
- **P@5 (Precision at 5)**: Target >0.85 for retrieval
- **Latency P95**: Target <5 seconds for standard queries

Use `scripts/benchmark_pipeline.py` for end-to-end testing.

### Code Organization

**Backend Structure**:
- `app/pipeline/` - Public API entry point (`RAGPipeline`)
- `app/orchestration/` - Execution coordination and flow control
- `app/agents/<component>/` - Component implementations with service adapters
  - `service.py` - Adapter interface for orchestration
  - Other files - Actual implementation logic
- `app/domain/` - Shared contracts and types
- `app/api/` - FastAPI routes and HTTP layer
  - `app/api/routes/public/` - Public-facing endpoints
  - `app/api/routes/admin/` - Admin-only endpoints
  - `app/api/routes/operations/` - Operational/health endpoints
  - `app/api/routes/compatibility/` - Internal shared utilities (see below)
- `app/retrievers/` - Retrieval implementations (vector, BM25, hybrid)
- `app/core/` - Core configuration and utilities

**Internal APIs**:

The `app/api/routes/compatibility/` directory contains **internal shared utilities**, 
not deprecated backward-compatibility code. Key modules:

- `pipeline_compat.py` - Standard RAG pipeline contract used by:
  - `admin/ops.py` - Performance profiling and benchmarking
  - `public/sessions.py` - Message rerun functionality
  
Despite the directory name, these are **active internal APIs** providing standardized 
interfaces for RAG pipeline execution across different services.

**Frontend Structure**:
- `frontend/src/pages/` - Page components (ChatPage, LoginPage)
- `frontend/src/features/` - Feature-specific logic
- `frontend/src/stores/` - Zustand state management
- `frontend/src/services/` - API clients
- `frontend/src/i18n/` - Internationalization (zh/en)

**Note**: The `app/agents/` directory name is historical - it houses components, not autonomous agents.

### Testing Strategy

- **Unit tests** (`-m unit`): Individual component logic
- **Integration tests** (`-m integration`): End-to-end workflow tests
- **Performance tests** (`-m performance`): Latency benchmarks

Mock external LLM calls in unit tests. Use `pytest-asyncio` for async tests.

## Important Notes

- **Conda environment is mandatory**: Dependencies assume conda-managed packages
- **Do not commit** files in `.gitignore`: `internal_docs/`, `.env`, `data/chroma/`, logs
- **Document organization**: Use `docs/development/daily-logs/YYYY-MM-DD/` for daily work logs. Run `python scripts/create_daily_log.py` to create today's log structure.
- **Bilingual system**: UI and responses support Chinese/English. Language detection is automatic via `language_analytics.py` (100% Chinese or 100% English, no mixing)
- **SSE streaming**: Real-time status updates use Server-Sent Events (see `app/api/routes/enhanced_query.py`)
- **Retry logic**: Retrieval retries retain their existing fallback policy; answer regeneration is capped at one retry per request
- **Circuit breaker**: Opens after 5 consecutive failures, closes after 60s cooldown
- **Session management**: Frontend supports session rename and pin features (added 2026-08-16). See `docs/development/daily-logs/2026-08-16/` for implementation details.
- **Enhanced Clarification System** (added 2026-08-17): Dynamic 2-10 round clarification based on intent complexity. Key service: `app/agents/router/enhanced_service.py`. See daily logs for details.
- **State management**: Frontend uses Zustand for global state, not Redux or Context API

## Common Issues

**"ModuleNotFoundError"**: Verify conda environment is activated
**"ChromaDB not found"**: Run `python scripts/init_db.py` to initialize vector store
**"Neo4j connection failed"**: Neo4j is optional; system falls back to vector-only retrieval
**Frontend CORS errors**: Ensure backend is running on port 8000

## Documentation Management

### Daily Work Logs

All daily work should be documented in `docs/development/daily-logs/YYYY-MM-DD/`:

```bash
# Create today's log structure
python scripts/create_daily_log.py

# Create specific date log
python scripts/create_daily_log.py --date 2026-08-18
```

Each day should include:
- `plan.md` - Daily goals and tasks
- `implementation.md` - Code changes and technical details
- `decisions.md` - Technical decisions and rationale
- `summary.md` - Completion status and lessons learned

**Important**: Keep project clean by moving all temporary documentation (from `app/docs/`, `frontend/docs/`, etc.) into the corresponding date folder at end of day. See [docs/development/daily-logs/README.md](docs/development/daily-logs/README.md) for detailed guidelines.
