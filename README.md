# Multi-Agent Local RAG

A local multi-agent RAG system with:

- FastAPI backend
- React + Vite frontend
- Hybrid retrieval (Vector + BM25 + Reranker)
- Neo4j graph retrieval
- Session history and prompt management
- Per-user data isolation (with optional admin public sharing)
- Admin ops for RAG/Agent strategy governance (profile/canary/shadow/rollback/benchmark)

## Features

- Multi-session chat with streaming responses
- PDF/image upload and indexing
- Prompt template create/check/update/delete
- Admin user/role/status management and audit logs
- Runtime strategy operations:
  - retrieval profile: `baseline` / `advanced` / `safe`
  - canary release by percentage
  - shadow traffic sampling and run logs
  - one-click runtime rollback
  - benchmark/replay trend tracking
  - session-level strategy lock
  - prompt versioning + approval + rollback
- Security controls:
  - user-level session/document isolation
  - retrieval allowlist by visible sources
  - admin upload visibility: `private` or `public`
  - safer file-inventory answers (never leak system/internal info)

## Project Structure

```text
app/            backend services and APIs
frontend/       React frontend
scripts/        helper scripts
tests/          unit/integration tests
```

## Quick Start

### 1) Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -U pip
pip install -e .
cp .env.example .env
docker compose up -d neo4j
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2) Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Open: `http://127.0.0.1:5173/app`

### 3) Workflow Visual + Low-Code (Optional)

- LangGraph Studio config is included via `langgraph.json`.
- n8n is available in `docker-compose.yml` as service `n8n`.
- Setup guide: [`docs/workflow_lowcode_setup.md`](./docs/workflow_lowcode_setup.md)
- Production self-check: [`docs/production_readiness_checklist.md`](./docs/production_readiness_checklist.md)

## Production Frontend Build

```bash
cd frontend
npm install
npm run build
```

Then open: `http://127.0.0.1:8000/app`

## OCR Notes (Windows)

Set in `.env`:

```env
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
TESSERACT_LANG=chi_sim+eng
```

## Security Notes

- `.env`, local runtime data, and temporary test artifacts are excluded from git via `.gitignore`.
- Upload visibility:
  - non-admin users: always `private`
  - admin users: can choose `private` / `public`
- Retrieval only uses allowed sources for the current user.

## Admin Ops Endpoints

- `GET/POST /admin/ops/retrieval-profile`
- `POST /admin/ops/canary`
- `GET/POST /admin/ops/shadow`
- `GET /admin/ops/shadow/runs`
- `POST /admin/ops/rollback`
- `POST /admin/ops/ab-compare`
- `POST /admin/ops/replay-history`
- `GET /admin/ops/replay/trends`
- `GET /admin/ops/index-freshness`
- `POST /admin/ops/autotune`
- `POST /admin/ops/benchmark/run`
- `GET /admin/ops/benchmark/trends`

## License

MIT. See [LICENSE](./LICENSE).
