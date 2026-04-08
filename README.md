# Multi-Agent Local RAG

A local multi-agent RAG system with:

- FastAPI backend
- React + Vite frontend
- Hybrid retrieval (Vector + BM25 + Reranker)
- Neo4j graph retrieval
- Session history and prompt management
- Per-user data isolation (with optional admin public sharing)

## Features

- Multi-session chat with streaming responses
- PDF/image upload and indexing
- Prompt template create/check/update/delete
- Admin user/role/status management and audit logs
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

## License

MIT. See [LICENSE](./LICENSE).
