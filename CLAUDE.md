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

**Linting and Formatting**
```bash
ruff check .                        # Lint check
ruff format .                       # Format code
```

Note (2026-08-28): `tests/` and `scripts/` were cleared ahead of the v0.7 rewrite — both
will be rebuilt against the new architecture rather than patched. There is currently no
test suite and no `scripts/init_db.py`.

Note (2026-08-29): A backend agent audit found several components documented above
that no longer matched the running code — an orphaned router/clarification rewrite
(`app/agents/router/{enhanced_service,hybrid_clarification,accuracy,frontend_integration,validator,adapter,pipeline}.py`),
an orphaned RAG fusion/vector duplicate (`app/agents/rag/{fusion.py::fuse_evidence,enhanced_vector.py}`),
an orphaned second quality-scoring engine (`app/agents/validation/quality_orchestrator.py`),
and an unreachable ReAct tool loop (`app/agents/tool/react.py`). All were deleted; the
claims above were corrected to describe what actually runs today.

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
5. **Tool Runner** - Governed connector actions. Today this means one action: disabling a connected integration by name, matched via regex against the raw question (`app/agents/tool/service.py`). Multi-hop/ReAct-style tool reasoning is not implemented; an earlier unreachable implementation (`app/agents/tool/react.py`) was removed on 2026-08-29.
6. **Finalizer** - Quality validation and safety checks

### Pipeline Profile

The system currently runs a single profile:

- **advanced**: Multi-hop reasoning, web research, and full quality validation

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
2. **Retrieval quality scoring**: `app/agents/rag/relevance.py` implements a local-LLM (Ollama) batch relevance scorer, but it currently has no callers anywhere in the request pipeline — retrieval results are not quality-scored in production today.
3. **Answer validation**: Citation completeness, hallucination detection, NLI checks
4. **Safety checks**: Regex-based PII/secret redaction (API keys, private keys, SSNs, credit card numbers, passwords, emails, phone numbers) via `app/services/answer_safety.py` and `app/agents/validation/rules.py`. There is no content-moderation/toxicity filter and no bias-detection implementation.

**Citation-First Principle**: Factual claims must include inline citations `[doc_id:page]` during generation.

**Note**: Quality validation is adjustable via profile settings within the `advanced` profile.

### Retrieval Strategy

**Hybrid Retrieval** ([app/retrievers/hybrid_retriever.py](app/retrievers/hybrid_retriever.py)):
- **Vector search**: Sentence-Transformers BGE-M3 embeddings → ChromaDB
- **BM25 search**: Jieba tokenization → Rank-BM25
- **Fusion**: Reciprocal Rank Fusion (RRF)
- **Reranking**: BGE-Reranker-V2-M3 (top 5 results)
- **Dynamic Top-K**: A complexity-adaptive calculator exists (`app/retrievers/hybrid/adaptive_params.py`, effective range ~6-16 results) but is only wired into the ReAct tool-search path and the offline `candidate_collection.py` pipeline. The default knowledge-node retrieval path used for ordinary chat queries currently retrieves a fixed `k=6` per source.

### Configuration System

**Essential config files** in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds. Only read when `ENABLE_CALIBRATION=true` (off by default); with calibration disabled, routing relies solely on the LLM classifier's own confidence output.

**Runtime config**: [app/core/config.py](app/core/config.py) intentionally does **not** read a root
`.env` file — it reads `.runtime/{APP_ENV}.env`, generated by
`deploy/scripts/config.py render` from `config/env/` + `config/profiles/` (or a file pointed to by
`RUNTIME_ENV_FILE`). Setting values in a root `.env` has no effect; export real environment
variables or run the render step first.

**Additional config**: [app/agents/shared/config.py](app/agents/shared/config.py) contains component-specific settings (currently undergoing simplification - many constants are legacy tuning parameters that will be consolidated or removed)

### Technology Stack

**Backend**: FastAPI + LangChain
**Vector Store**: ChromaDB (local, persistent)
**Graph Store**: Neo4j (optional)
**Database**: SQLite (default, `DATABASE_URL`), with PostgreSQL (`asyncpg`) supported for production
**Frontend**: React 18 + TypeScript + Vite + Zustand (state) + i18next (i18n)
**Models**: OpenAI GPT-5.5 (primary, `OPENAI_CHAT_MODEL`), Claude Haiku (multimodal image description/OCR triage in `app/services/multimodal/image_processor.py`; not used for retrieval-quality batch scoring, see Quality Assurance section), Sentence-Transformers (embeddings)
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

No test suite currently exists (`tests/` was cleared ahead of the v0.7 rewrite). It will be
rebuilt against the new architecture rather than patched onto the old one.

## Important Notes

- **Conda environment is mandatory**: Dependencies assume conda-managed packages
- **Do not commit** files in `.gitignore`: `internal_docs/`, `.env`, `data/chroma/`, logs
- **Document organization**: Use `docs/development/daily-logs/YYYY-MM-DD/` for daily work logs (create manually).
- **Bilingual system**: UI and responses support Chinese/English. Language detection is automatic via `language_analytics.py` (100% Chinese or 100% English, no mixing)
- **SSE streaming**: Real-time status updates use Server-Sent Events (see `app/api/routes/enhanced_query.py`)
- **Retry logic**: Retrieval retries retain their existing fallback policy; answer regeneration is capped at one retry per request
- **Circuit breaker**: Opens after 5 consecutive failures, closes after 60s cooldown
- **Session management**: Frontend supports session rename and pin features (added 2026-08-16). See `docs/development/daily-logs/2026-08-16/` for implementation details.
- **Clarification System** (added 2026-08-17, revised 2026-08-29): Dynamic clarification based on intent complexity, capped at 0-7 rounds depending on intent (`rag_design`: 7, `document_comparison`: 5, others: 5, already-complete: 0). Key services: `app/agents/clarification/service.py` and `rules.py`, wired as both the LangGraph `clarification` node and the resumable `/api/v1/clarification/check` HTTP endpoint (`app/api/routes/public/clarification.py`) — the two share one implementation. See daily logs for details.
- **State management**: Frontend uses Zustand for global state, not Redux or Context API

## Common Issues

**"ModuleNotFoundError"**: Verify conda environment is activated
**"Neo4j connection failed"**: Neo4j is optional; system falls back to vector-only retrieval
**Frontend CORS errors**: Ensure backend is running on port 8000

## Documentation Management

### Daily Work Logs

All daily work should be documented in `docs/development/daily-logs/YYYY-MM-DD/` (create the
folder and files manually — `scripts/create_daily_log.py` was removed ahead of the v0.7 rewrite).

Each day should include:
- `plan.md` - Daily goals and tasks
- `implementation.md` - Code changes and technical details
- `decisions.md` - Technical decisions and rationale
- `summary.md` - Completion status and lessons learned

**Important**: Keep project clean by moving any temporary documentation created elsewhere in the repo into the corresponding date folder at end of day. See [docs/development/daily-logs/README.md](docs/development/daily-logs/README.md) for detailed guidelines.
