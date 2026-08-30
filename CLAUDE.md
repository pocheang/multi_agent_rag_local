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

Note (2026-08-28): `tests/` and `scripts/` were cleared ahead of the v0.7 rewrite. `scripts/`
is still empty (no `scripts/init_db.py`); `tests/` is being rebuilt incrementally alongside
bug fixes — see Testing Strategy below.

**Tests and lint**
```bash
make test                           # pytest -q
make lint                           # ruff check . && ruff format --check .
```

Note (2026-08-29): A backend agent audit found several components documented above
that no longer matched the running code — an orphaned router/clarification rewrite
(`app/agents/router/{enhanced_service,hybrid_clarification,accuracy,frontend_integration,validator,adapter,pipeline}.py`),
an orphaned RAG fusion/vector duplicate (`app/agents/rag/{fusion.py::fuse_evidence,enhanced_vector.py}`),
an orphaned second quality-scoring engine (`app/agents/validation/quality_orchestrator.py`),
and an unreachable ReAct tool loop (`app/agents/tool/react.py`). All were deleted; the
claims above were corrected to describe what actually runs today.

Note (2026-08-29, second pass): A full-backend audit found the chat path was not
persisting messages, conversation context was filled but never read, the query
endpoint never returned its execution_id, the `graph` route never queried the
graph, and 184 modules (~13,000 lines) had zero importers. All were fixed or
deleted; `app/` went from 583 to 371 Python files and Settings from 261 to 216
fields. See `docs/superpowers/plans/2026-08-29-backend-full-audit-remediation.md`
for the plan, what was deliberately left dormant, and what remains open.

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

The system runs a single profile, **advanced** (web research and full quality
validation). `ExecutionPolicy.for_profile` in `app/orchestration/policies.py` is the
only place that decides what a profile enables. A parallel set of descriptors in
`app/pipeline/profiles.py` (`ProfileCapabilities`, `CapabilityBudget`,
`PROFILE_DEFINITIONS`) had no readers and had drifted into contradicting the policy;
it was deleted on 2026-08-29, leaving only the `PipelineProfile` enum.

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
2. **Retrieval quality scoring**: none. A local-LLM (Ollama) batch relevance scorer existed in `app/agents/rag/relevance.py` with no callers anywhere in the request pipeline; it was deleted on 2026-08-29. Retrieval results are not quality-scored.
3. **Answer validation**: Citation completeness, hallucination detection, NLI checks
4. **Safety checks**: Two independent regex redaction paths, with different pattern sets.
   `app/services/answer_safety.py` runs on every finalized answer and covers OpenAI-style
   keys, AWS access key ids, private-key headers, and `password=`/`token=` assignments;
   it is gated by `ANSWER_SAFETY_SCAN_ENABLED`. `app/agents/validation/rules.py`
   additionally matches SSN, credit-card, email and phone patterns, and runs inside the
   validation cascade reached through the verifier. There is no content-moderation/toxicity
   filter and no bias-detection implementation.

**Citation-First Principle**: Factual claims must include inline citations `[doc_id:page]` during generation.

**Dormant by design (2026-08-29)**: the following exist and are reachable but are
switched off on the live request path. Turning any of them on is a cost/latency
decision, not a bug fix — do not "fix" them by flipping the flag.

- **Fact verification and self-review**: `app/agents/synthesizer/service.py` calls
  `synthesize_answer(..., enable_fact_verification=False, enable_self_review=False)`.
- **KnowledgeOrchestrator as top-level retrieval assembler**:
  `KNOWLEDGE_ORCHESTRATOR_ENABLED` defaults to false, so retrieval goes through
  `RAGAgentService`, which delegates to the same orchestrator internally.
- **Router confidence calibration**: `ENABLE_CALIBRATION` defaults to false, so
  `config/router_calibration.json` is not read.
- **Clarification round caps**: hardcoded per intent in
  `app/agents/clarification/rules.py::_MAX_ROUNDS`; there is no env override.

**Note**: Quality validation is controlled by `ExecutionPolicy`, not by per-profile
settings — see Pipeline Profile above.

### User Data Isolation

Retrieval is scoped, not just filtered afterwards (fixed 2026-08-30). Two properties
carry it, and both are pinned by `tests/security/`:

- `privacy_permission` (`app/orchestration/langgraph/nodes.py`) resolves the caller's
  `AccessScope` and **rewrites `request.source_scope` from it**, so no later stage can
  be handed a wider range than the resolver authorized — whatever the API layer passed.
  This is why `pipeline_contract.py` may still pass `allowed_sources=None` harmlessly.
- `similarity_search` fails closed: a missing `allowed_sources` raises rather than
  searching every tenant's corpus, and an *empty* one returns nothing. Those two cases
  must stay distinct — collapsing them is what previously turned "this user has no
  documents" into an unrestricted search.

`evidence_is_authorized` (`app/privacy/dlp.py`) remains the output-side check. `web` and
`tool` evidence is exempt (not user documents); `memory` is checked against the
`memory://{tenant}/{user}/` namespace its store already enforces, not against
`allowed_sources`, which only ever holds document paths.

Counts of scope-dropped evidence are logged, never returned: they would tell a caller
how many documents *other* tenants hold on a topic.

An **empty** document scope (a user who has uploaded nothing) and a **missing** one are
different states and must stay so. Empty drops the document-backed retrievers but keeps
web — web results are not documents — and returns quietly; missing raises. Collapsing
them in either direction is a bug: one way silently removes web search from every new
user, the other turns "a caller bypassed the resolver" into a result that reads as "no
matches found". `KnowledgeOrchestrator._retrieve_source` skips only
`vector`/`bm25`/`graph`/`wiki`/`multimodal` on an empty scope; `RAGAgentService.retrieve`
matches that list rather than short-circuiting ahead of it.

The store adds a second, independent check: `similarity_search` takes an `OwnerScope` and
requires the chunk's own `owner_user_id`/`visibility`/`tenant_id` metadata to match, not
just its `source`. Source paths are *derived* from the visibility rules; owner metadata is
written independently at ingest, so requiring both narrows what a wrong source list can
reach. **This means chunks indexed before ingest wrote owner metadata are invisible once
the clause is on — `$eq` does not match an absent key (verified on chromadb 1.5.9). Reindex
any pre-existing store before deploying.** Every `similarity_search` call site must pass an
owner; `tests/security/test_no_unrestricted_retrieval.py` enumerates them via AST and keeps
the two genuinely caller-less ones in a documented allowlist. A partial guard would be
worse than none.

Documents are addressed by `document_id`, not filename: two users routinely hold a
`report.pdf`, so `/documents/{filename}` refuses whenever the name is ambiguous and
`/documents/by-id/{document_id}` is the form the frontend uses. A `?source=` query
parameter *narrows* the candidates a filename resolves to — it must never select one on
its own, which is what let an admin act on a file they could not even list. "No such
document" and "not yours" both return 404 on purpose: distinguishing them discloses that
someone else's document exists.

BM25 keeps one prebuilt index per access scope (`_load_scoped_bm25`, LRU), and separates
matching from ranking: a document is a candidate if it shares a term with the query, and
BM25 only orders the candidates. Do not reintroduce `score > 0` as the membership test —
BM25 IDF is negative for a term present in most documents, so in a small scope (one chunk,
now a routine case) every term scores below zero and matching documents get dropped. A
negative `bm25_score` in the output is normal and harmless: RRF fuses on rank, not score.

### Retrieval Strategy

**Hybrid Retrieval** ([app/retrievers/hybrid/retriever.py](app/retrievers/hybrid/retriever.py)):
- **Vector search**: Sentence-Transformers BGE-M3 embeddings → ChromaDB
- **BM25 search**: Jieba tokenization → Rank-BM25
- **Fusion**: Reciprocal Rank Fusion (RRF)
- **Graph retrieval**: runs for both the `graph` and `hybrid` routes (fixed 2026-08-29; `graph` previously degraded silently to vector+BM25)
- **Reranking**: BGE-Reranker-V2-M3 (top 5 results)
- **Dynamic Top-K**: A complexity-adaptive calculator exists (`app/retrievers/hybrid/adaptive_params.py`, effective range ~6-16 results) but applies only inside `candidate_collection.py`. The knowledge-node path used for ordinary chat queries hardcodes `top_k=6` per source (`app/agents/rag/service.py`), so `DYNAMIC_RETRIEVAL_ENABLED` and the `DYNAMIC_*_CAP` settings do not affect it.

### Configuration System

**Essential config files** in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds. Only read when `ENABLE_CALIBRATION=true` (off by default); with calibration disabled, routing relies solely on the LLM classifier's own confidence output.

**Runtime config**: [app/core/config.py](app/core/config.py) intentionally does **not** read a root
`.env` file — it reads `.runtime/{APP_ENV}.env`, generated by
`deploy/scripts/config.py render` from `config/env/` + `config/profiles/` (or a file pointed to by
`RUNTIME_ENV_FILE`). Setting values in a root `.env` has no effect; export real environment
variables or run the render step first.

`.runtime/` starts empty. Until `make config-render ENV=development` is run,
`Settings` falls back to its hardcoded defaults for every field — including
`MODEL_BACKEND=local`. Run the render step (or export real environment variables)
before treating any configured value as active.

**Additional config**: [app/agents/shared/config.py](app/agents/shared/config.py) contains component-specific settings (currently undergoing simplification - many constants are legacy tuning parameters that will be consolidated or removed)

### Technology Stack

**Backend**: FastAPI + LangChain
**Vector Store**: ChromaDB (local, persistent)
**Graph Store**: Neo4j (optional)
**Database**: SQLite only. Each store opens its own `sqlite3` connection
(`app/services/auth/auth_service.py`, `app/services/sessions/history.py`,
`app/services/sessions/metadata_db.py`, `app/services/prompts/store.py`,
`app/wiki/store.py`, `app/retrievers/stores/vector.py`). There is no shared connection
pool and no PostgreSQL support: an async SQLAlchemy pool existed but was never used by
any business code and was removed on 2026-08-29, along with the `asyncpg`/`aiosqlite`
dependencies and `DATABASE_URL`.
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
  - `app/api/routes/internal/` - Contracts shared between route modules, never registered as routers
- `app/retrievers/` - Retrieval implementations (vector, BM25, hybrid)
- `app/core/` - Core configuration and utilities

**Internal APIs**:

`app/api/routes/internal/pipeline_contract.py` exposes the standard RAG pipeline
execution contract used by:

- `admin/ops.py` - Performance profiling and benchmarking
- `public/sessions.py` - Message rerun functionality

Note (2026-08-29): this module and the live chat/SSE routes previously lived in
`app/api/routes/compatibility/`, whose name implied deprecated code and repeatedly
misled readers. The chat endpoint moved to `public/query.py`, the SSE endpoint to
`public/orchestration.py`, and this contract to `internal/`. No HTTP path changed.

**Frontend Structure**:
- `frontend/src/pages/` - Page components (ChatPage, LoginPage)
- `frontend/src/features/` - Feature-specific logic
- `frontend/src/stores/` - Zustand state management
- `frontend/src/services/` - API clients
- `frontend/src/i18n/` - Internationalization (zh/en)

**Note**: The `app/agents/` directory name is historical - it houses components, not autonomous agents.

### Testing Strategy

`tests/` was cleared ahead of the v0.7 rewrite and is being rebuilt incrementally: each bug
fix lands with the regression test that would have caught it, rather than as a separate
back-filling effort. As of 2026-08-30 there are 174 tests covering the chat round trip,
conversation context, graph routing, clarification, the async load guard, engine reuse,
answer safety, retrieval module-global isolation, and a guard that every Settings field has
a reader.

`tests/security/` (112 of those) pins the user-data isolation invariants — see
`docs/superpowers/plans/2026-08-29-user-data-isolation.md`. That plan is complete
(phases 0-4) and all 8 of its `xfail(strict=True)` markers are cleared; keep using the same
pattern for a new gap, so a fix that makes the test pass fails the suite until the marker
is removed. `test_no_unrestricted_retrieval.py`
is a ratchet rather than a plain assertion: `KNOWN_OFFENDERS` records how many
unrestricted `similarity_search` calls each module has, and the count may only go down.
It is currently empty.

User questions must not reach the logs: `question_ref()`
(`app/services/observability/log_safety.py`) gives a stable digest instead, and
`tests/security/test_no_question_text_in_logs.py` enumerates every `logger.*` call via AST
to keep it that way. Truncating (`question[:50]`) does not count as redaction.

`pytest` is configured in `pyproject.toml` (`testpaths = ["tests"]`, strict asyncio mode).
CI runs it on every push and pull request (`.github/workflows/ci.yml`), together with ruff
and an OpenAPI endpoint census that fails if a refactor silently drops routers.

The frontend has vitest tests too (`frontend/src/**/*.test.ts`, run by the `frontend` CI
job). `storeReset.test.ts` covers the Zustand `reset()` that App.tsx calls on logout and on
any identity change: the stores outlive a logout, so a field added to a store but forgotten
in its `INITIAL_STATE` would show the next person on a shared browser the previous user's
data. The test discovers fields rather than listing them, so it catches that drift.

Note: do not use `len(app.routes)` to count endpoints. FastAPI 0.138+ stores an
`_IncludedRouter` wrapper in `app.routes` instead of flattening child routes, so that number
varies by version. Count OpenAPI operations instead; the current baseline is 151 (CI asserts a >= 140 floor).

## Important Notes

- **Conda environment is mandatory**: Dependencies assume conda-managed packages
- **Do not commit** files in `.gitignore`: `internal_docs/`, `.env`, `data/chroma/`, logs
- **Document organization**: Use `docs/development/daily-logs/YYYY-MM-DD/` for daily work logs (create manually).
- **Bilingual system**: UI and responses support Chinese/English. Language detection is automatic via `language_analytics.py` (100% Chinese or 100% English, no mixing)
- **SSE streaming**: Execution-trace events are served by `app/api/routes/public/orchestration.py`
  (`GET /api/v1/orchestration/executions/{execution_id}/events`). The query endpoint returns
  `metadata.execution_id`, which the client uses to subscribe. The stream replays a finished
  run's stage events; it is not a token-level answer stream.
- **Retry logic**: Retrieval retries retain their existing fallback policy; answer regeneration is capped at one retry per request
- **Circuit breaker**: Opens after 5 consecutive failures, closes after 60s cooldown
- **Admin ops benchmark/replay corpus** (fixed 2026-08-30): `POST /admin/ops/benchmark/run` and
  `POST /admin/ops/replay/run` run their queries under the requesting admin's identity. They used to
  pass no actor at all, and every query died in the pipeline's first node — `privacy_permission`
  resolves an access scope and fails closed with "authenticated user identity is required". The
  consequence of the fix is that a run measures the corpus that admin can see (the shared
  `data/docs/` set plus their own and public documents) rather than a fixed corpus, so trends from
  two admins with different visible documents are not directly comparable. Scoping the runs to
  `data/docs/` instead was rejected: it would measure something no real query ever does, and would
  need a synthetic actor, reopening the fail-closed hole the resolver exists to close.
- **Benchmark query set** (2026-08-30): `run_benchmark` reads `data/eval/benchmark_queries.txt` if
  present, otherwise the tracked default `config/eval/benchmark_queries.txt`. It previously read only
  the `data/` path, which is gitignored runtime state — absent on every checkout where nobody placed
  it by hand, so the job died with "benchmark query set is empty" inside the background queue, where
  the endpoint's 202 response never surfaces it. `#` starts a comment in that file. The shipped set is
  a corpus-agnostic starter: it exercises pipeline latency and route branches, but grounding and
  citation numbers only mean something once the queries match documents actually in the corpus.
- **Session management**: Frontend supports session rename and pin features (added 2026-08-16). See `docs/development/daily-logs/2026-08-16/` for implementation details.
- **Clarification System** (added 2026-08-17, revised 2026-08-29): Dynamic clarification based on intent complexity, capped at 0-7 rounds depending on intent (`rag_design`: 7, `document_comparison`: 5, others: 5, already-complete: 0). Key services: `app/agents/clarification/service.py` and `rules.py`, wired as both the LangGraph `clarification` node and the resumable `/api/v1/clarification/check` HTTP endpoint (`app/api/routes/public/clarification.py`) — the two share one implementation. Questions exist in Chinese and English (`_QUESTIONS_ZH` / `_QUESTIONS_EN`), selected from `force_language` or the query's script. Inside the pipeline the clarifier has no collected context and therefore always asks; the node logs that and continues with the original query rather than failing the request — interactive clarification belongs to the HTTP endpoint.
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
