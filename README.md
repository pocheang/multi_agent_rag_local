# Multi-Agent Local RAG

[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB.svg)](https://react.dev/)

Enterprise-oriented, local-first RAG platform with multi-agent orchestration, hybrid retrieval, graph enhancement, admin governance, and streaming chat.

This repository packages a FastAPI backend, a React frontend, and a modular retrieval pipeline designed for private knowledge bases, internal copilots, and controlled enterprise AI workflows.

## Executive Summary

- Multi-agent query orchestration built on LangGraph
- Hybrid retrieval with vector search, BM25, fusion, and reranking
- Optional Neo4j knowledge graph enrichment
- Local-first document ingestion with OCR support
- Role-based access control, session isolation, and admin operations
- Runtime controls for retrieval profiles, canary, rollback, benchmarking, and replay
- Streaming chat UX with session history and prompt management

## Target Use Cases

- Internal knowledge assistant for enterprise teams
- Private document Q&A over PDF, image, and text corpora
- RAG evaluation and retrieval strategy experimentation
- Controlled AI operations with auditability and rollback
- Hybrid local and hosted model deployments

## System Overview

### Core Components

- `app/api/`: FastAPI application, route modules, middleware, dependencies
- `app/graph/`: LangGraph workflow, routing logic, streaming helpers
- `app/agents/`: router, retrieval, graph, web, and synthesis agents
- `app/retrievers/`: hybrid retrieval pipeline and ranking logic
- `app/services/`: auth, runtime governance, caching, resilience, memory, prompts
- `app/ingestion/`: loaders, chunking, OCR, indexing
- `frontend/`: React + Vite user interface
- `tests/`: backend and workflow regression coverage

### Request Flow

1. User authenticates and starts or resumes a session.
2. Query enters the FastAPI layer and shared dependencies initialize context.
3. LangGraph routes the request through retrieval, graph, web, and synthesis steps.
4. Hybrid retrieval gathers evidence from Chroma, BM25, and optional graph context.
5. Safety and grounding logic shape the final answer.
6. The frontend receives streamed or non-streamed output with citations and metadata.

## API Surface

The main backend entry point is `app.api.main:app`.

### Major Route Groups

- `/auth`: register, login, logout, current user
- `/query`: synchronous and streaming query endpoints
- `/sessions`: session CRUD, strategy lock, memory operations
- `/documents`: document inventory, deletion, reindex, upload
- `/prompts`: prompt templates, validation, versions, approval, rollback
- `/admin/users`: user lifecycle and audit operations
- `/admin/ops`: retrieval profile, canary, rollback, benchmark, replay, reports
- `/admin/model-settings` and `/user/api-settings`: runtime model settings
- `/health`, `/ready`, `/metrics`: health and readiness endpoints

## Architecture Characteristics

### Retrieval

- Dense retrieval through ChromaDB
- Sparse retrieval through BM25
- Reciprocal Rank Fusion for candidate blending
- Optional reranking with `BAAI/bge-reranker-v2-m3`
- Parent-child chunk strategy for precision and answer context

### Orchestration

- LangGraph-based node orchestration
- Router, vector, graph, web, and synthesis stages
- Streaming support for partial answer delivery
- Runtime-safe wrappers and fallback handling

### Governance and Safety

- RBAC and user-scoped data access
- Approval-token flow for privileged admin creation
- Audit logging for sensitive operations
- Retrieval profiles, canary routing, and rollback support
- Query guards, quota controls, and resilience utilities

## Repository Layout

```text
.
|-- app/
|   |-- agents/
|   |-- api/
|   |-- core/
|   |-- graph/
|   |-- ingestion/
|   |-- retrievers/
|   |-- services/
|   `-- tools/
|-- configs/
|-- data/
|-- docs/
|-- frontend/
|-- scripts/
`-- tests/
```

## Multi-Agent Workflow

The system uses **LangGraph** to orchestrate a sophisticated multi-agent workflow:

1. **Router Agent** - Analyzes query intent and determines routing strategy
2. **Vector RAG Agent** - Performs hybrid retrieval (vector + BM25 + reranking)
3. **Graph RAG Agent** - Queries Neo4j knowledge graph for entity relationships
4. **Web Research Agent** - Conducts web search when local knowledge is insufficient
5. **Synthesis Agent** - Synthesizes final answer with grounding and safety checks

### Tiered Execution System

Queries are automatically classified into three tiers based on complexity:

| Tier | Use Case | Retrieval | Max Time | Tokens | Web Fallback |
|------|----------|-----------|----------|--------|--------------|
| **Fast** | Simple factual queries, single-entity lookup | top_k=5, rerank=3 | 800ms | 300 | Disabled |
| **Balanced** | Default for most queries, moderate complexity | top_k=10, rerank=5 | 2000ms | 800 | Conditional |
| **Deep** | Multi-hop reasoning, comprehensive answers | top_k=20, rerank=10 | 5000ms | 1500 | Enabled |

**Load-Based Degradation**: System automatically downgrades tiers when load >80% for stability.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose for Neo4j
- One model backend:
  - Ollama
  - OpenAI
  - Anthropic

## Quick Start

### 1. Backend Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
copy .env.example .env
```

### 2. Configure Environment

Edit `.env` and set the backend you want to use.

Example for OpenAI:

```bash
MODEL_BACKEND=openai
OPENAI_API_KEY=your_api_key
OPENAI_CHAT_MODEL=gpt-4-turbo
OPENAI_EMBED_MODEL=text-embedding-3-small
```

Example for Ollama:

```bash
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### 3. Start Neo4j

```bash
docker compose up -d neo4j
```

### 4. Run the Backend

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"
```

### 5. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/app`.

## Document Ingestion

- Put source files under `data/docs`
- Or upload through the web UI / API
- Run manual ingestion when needed:

```bash
python scripts/ingest.py
```

Useful related settings:

- `AUTO_INGEST_ENABLED`
- `DATA_DIR`
- `CHROMA_PERSIST_DIR`
- `CORPUS_STORE_PATH`
- `PARENT_STORE_PATH`

## Key Configuration Domains

### Model and Runtime

- `MODEL_BACKEND`
- `OPENAI_*`
- `ANTHROPIC_*`
- `OLLAMA_*`
- `QUERY_REQUEST_TIMEOUT_MS`

### Retrieval

- `TOP_K`
- `VECTOR_TOP_K`
- `BM25_TOP_K`
- `ENABLE_RERANKER`
- `RERANKER_MODEL_NAME`
- `RETRIEVAL_PROFILE`

### Storage

- `CHROMA_PERSIST_DIR`
- `DATA_DIR`
- `APP_DB_PATH`
- `SESSIONS_DIR`
- `UPLOADS_DIR`

### Security

- `AUTH_TOKEN_TTL_HOURS`
- `ADMIN_CREATE_APPROVAL_TOKEN_HASH`
- `API_SETTINGS_ENCRYPTION_KEY`
- `API_BASE_URL_ALLOWLIST`

### OCR and Media

- `TESSERACT_CMD`
- `TESSERACT_LANG`
- `OCR_PREPROCESS_ENABLED`
- `IMAGE_CAPTION_ENABLED`

## Operations

### Backend Tests

```bash
pytest -q
```

### Quality Gate

```bash
python scripts/ci_quality_gate.py
```

### Frontend Build

```bash
cd frontend
npm run build
```

### Example Operational Scripts

- `scripts/benchmark_pipeline.py`
- `scripts/load_test_query.py`
- `scripts/eval_retrieval.py`
- `scripts/chaos_probe.py`

## Security Notes

- Do not commit `.env`
- Prefer hashed admin approval token over plaintext token
- Review upload limits and API allowlists before production use
- Validate cross-user isolation and admin endpoint restrictions in every release
- Treat model-provider credentials as environment-scoped secrets

## Documentation

Start with the documentation hub: [docs/README.md](./docs/README.md)

Recommended reading order:

1. [docs/README.md](./docs/README.md)
2. [docs/production_readiness_checklist.md](./docs/production_readiness_checklist.md)
3. [docs/DOCUMENTATION_STANDARD.md](./docs/DOCUMENTATION_STANDARD.md)
4. [CHANGELOG.md](./CHANGELOG.md)
5. [CLAUDE.md](./CLAUDE.md)

Historical release and refactoring reports are retained under `docs/` for audit and traceability, but they should be treated as point-in-time records rather than the primary operational source of truth.

## Known Documentation Note

The repository contains historical documents and release artifacts from multiple milestones. Core entry documents have been normalized for enterprise use, while older milestone reports remain preserved as historical records.

## License

MIT. See [LICENSE](./LICENSE).

---

**Made with ❤️ by the Bronit Team**
