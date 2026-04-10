# Multi-Agent Local RAG

Current version: `0.2.2.1`

Local-first multi-agent RAG system with:

- FastAPI backend
- React + Vite frontend
- Hybrid retrieval (`Vector + BM25 + Reranker`)
- Neo4j graph retrieval
- Session/prompt/document management
- Admin ops for RAG/Agent governance and runtime resilience

## What's New in 0.2.2.1

### Added
- Runtime resilience modules: alerting, background queue, bulkhead isolation, hybrid executor, query guard, quota guard, and query-result cache.
- Operational scripts for chaos probing, load/performance validation, and data migrations.
- Concurrency regression test coverage (`tests/test_concurrency_regression.py`).

### Changed
- Workflow orchestration, graph streaming, and Neo4j integration were updated to support stronger runtime control behavior.
- API and schema/model contracts were expanded for governance and reliability flows.
- CI quality-gate checks were improved for release readiness.

### Release Notes
- Changelog entry: [`CHANGELOG.md`](./CHANGELOG.md)
- GitHub release (`v0.2.2.1`): <https://github.com/pocheang/multi_agent_rag_local/releases/tag/v0.2.2.1>

## Core Features

- Multi-session chat with streaming responses
- PDF/image upload and indexing
- Prompt template management
- Admin user/role/status/audit management
- Retrieval source allowlist and user-level isolation

## Quick Start

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -U pip
pip install -e .
cp .env.example .env
docker compose up -d neo4j
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"
```

### Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Open: `http://127.0.0.1:5173/app`

### Health Check

- API health: `GET /health`
- readiness: `GET /ready`
- metrics (Prometheus text format): `GET /metrics`

## Admin Ops API (RAG/Agent)

- profile/canary/shadow:
  - `GET/POST /admin/ops/retrieval-profile`
  - `POST /admin/ops/canary`
  - `POST /admin/ops/feature-flags`
  - `GET/POST /admin/ops/shadow`
  - `GET /admin/ops/shadow/runs`
- rollback/evaluation:
  - `POST /admin/ops/rollback`
  - `POST /admin/ops/ab-compare`
  - `POST /admin/ops/replay-history`
  - `GET /admin/ops/replay/trends`
  - `POST /admin/ops/benchmark/run`
  - `GET /admin/ops/benchmark/trends`
- reliability/quality:
  - `GET /admin/ops/alerts`
  - `GET /admin/ops/index-freshness`
  - `POST /admin/ops/autotune`

## Helpful Docs

- Workflow visual + n8n: [`docs/workflow_lowcode_setup.md`](./docs/workflow_lowcode_setup.md)
- Production checklist: [`docs/production_readiness_checklist.md`](./docs/production_readiness_checklist.md)

## Test

```bash
pytest -q
```

## License

MIT. See [LICENSE](./LICENSE).
