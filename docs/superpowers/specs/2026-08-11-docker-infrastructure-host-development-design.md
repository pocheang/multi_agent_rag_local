# Docker Infrastructure and Host Development Design

## Goal

Make QueryMind's core services runnable on Windows with infrastructure in Docker and the backend/frontend on the host. The supported local stack consists of Ollama, PostgreSQL, Redis, Neo4j, the FastAPI backend, and the Vite frontend.

## Scope

The implementation covers:

- Docker-managed Ollama, PostgreSQL, Redis, and Neo4j.
- Host-managed FastAPI on `127.0.0.1:8000` in the mandatory `rag-local` Conda environment.
- Host-managed Vite on `127.0.0.1:5173`.
- Ollama chat and embedding model initialization.
- Canonical development configuration generation into `.runtime/development.env`.
- PowerShell commands for starting, stopping, and inspecting the local stack.
- Repairs required for backend test collection, backend startup, frontend tests/build, and frontend development startup.

The implementation does not enable n8n, Prometheus, Grafana, Alertmanager, production TLS, or production hosting. It does not delete or reset existing local data or unrelated uncommitted changes.

## Architecture

Docker Compose owns only the four stateful infrastructure services. PostgreSQL, Redis, and Neo4j use named volumes. Ollama uses a named model volume and an NVIDIA GPU reservation compatible with Docker Desktop on Windows. The host backend connects to published infrastructure ports, while the host frontend sends relative requests through the Vite proxy to the backend.

The default Ollama models are `qwen2.5:7b-instruct` for chat and `nomic-embed-text` for embeddings. A documented `qwen2.5:3b-instruct` override is available if the GTX 1660 Ti's 6 GB of VRAM cannot run the 7B model reliably. Model downloads are performed by an idempotent initialization service after Ollama reports healthy.

## Components

### Canonical configuration

The source-controlled configuration layers are:

1. `config/env/base.env` for shared defaults.
2. `config/env/development.env.example` for safe development overrides.
3. `config/profiles/balanced.env` for retrieval and runtime strategy values.
4. `.runtime/generated-secrets.env` for locally generated secrets.
5. Process environment variables for explicit user overrides.

`deploy/scripts/config.py` merges these layers into `.runtime/development.env`. The generated file remains ignored by Git. Development addresses use the host-published endpoints:

- Ollama: `http://127.0.0.1:11434`
- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
- Neo4j HTTP/Bolt: `127.0.0.1:7474` and `bolt://127.0.0.1:7687`

The frontend uses an empty `VITE_API_BASE_URL`, keeping API requests same-origin through Vite's proxy and avoiding localhost/127.0.0.1 cookie inconsistencies.

### Docker infrastructure

A development infrastructure Compose definition exposes only the required local ports. Every long-running service has a concrete health check. The Ollama model initializer depends on Ollama health and exits successfully only after both configured models appear in the local model inventory.

Stopping the stack removes containers and networks owned by the QueryMind Compose project but preserves named volumes. No normal startup or stop command deletes models, database contents, graph data, or Redis persistence.

### Host processes

The backend is launched through the `rag-local` Conda environment with the generated dotenv file loaded before importing `app.api.main:app`. The frontend is launched from `frontend/` using its lockfile and local npm binaries. The start workflow checks prerequisites, renders configuration, starts infrastructure, waits for health, initializes the application database, and then starts the backend and frontend.

The helper workflow records only process IDs that it created. Its stop operation may terminate those recorded processes and the QueryMind infrastructure Compose project; it must not terminate unrelated Python, Node, Docker, or Ollama processes.

## Request and Data Flow

1. The browser opens `http://127.0.0.1:5173`.
2. Vite serves the React application and proxies API paths to `http://127.0.0.1:8000`.
3. FastAPI loads `.runtime/development.env` and handles authentication, document, session, and query requests.
4. Query execution enters through `RAGPipeline` and uses PostgreSQL, Redis, Neo4j, local Chroma data, and Ollama as required by the selected profile.
5. Ollama serves chat generation and embedding requests from its persistent model volume.

No new production query path may bypass `RAGPipeline`. Existing compatibility executors remain behind the pipeline.

## Code Repair Strategy

Existing uncommitted refactor work is treated as user-owned and preserved. Repairs are restricted to defects that block configuration, test collection, startup, build, or the defined core data flow.

Each behavioral repair follows a red-green cycle:

1. Reproduce the exact failure.
2. Identify the root cause and the working repository pattern.
3. Add the smallest regression test that fails for the identified defect.
4. Make the smallest production change that passes the regression test.
5. Run the focused test and then the relevant wider suite.

Known investigation targets are the missing canonical config layers, legacy compatibility exports removed during package verticalization, a graph execution circular import, an invalid chart extraction module path, and Vite configuration loading under the current Windows environment. These are investigation targets rather than assumed fixes.

## Error Handling

The startup workflow fails fast with a specific message when Conda, the `rag-local` environment, Docker Desktop, Docker Compose, Node/npm, a required file, or a required port is unavailable. It reports which service health check failed and shows the corresponding inspection command without exposing secret values.

Model initialization distinguishes an unavailable Ollama service from a model download failure. Backend readiness distinguishes process startup from dependency readiness. Frontend readiness requires an HTTP response and a successful proxied backend health request.

Generated secrets are never printed. Configuration validation reports missing key names only. Startup retries use health conditions with bounded timeouts rather than fixed sleeps.

## Verification

The implementation is accepted only when fresh commands demonstrate all applicable checks:

- Development configuration renders and validates.
- Docker Compose configuration validates.
- Ollama, PostgreSQL, Redis, and Neo4j report healthy.
- Ollama completes one chat request and one embedding request.
- Backend tests collect without errors.
- Focused regression tests pass, followed by the full backend test suite or a clearly reported evidence-based list of remaining unrelated failures.
- The backend imports and starts in `rag-local`; `/health` and `/ready` respond successfully.
- Frontend Vitest tests pass.
- TypeScript compilation and the Vite production build pass.
- The Vite development server responds on port 5173 and successfully proxies a backend health request.
- A clean start/status/stop/start cycle preserves Docker volumes and returns the same healthy state.

Any validation that depends on user documents is reported separately from core runtime readiness. Missing document content is not treated as a runtime defect.

## Safety and Compatibility

No existing files are reverted wholesale. Changes to already modified files are reviewed against their current working-tree content. No command deletes Docker volumes, local Chroma data, database files, downloaded models, or user configuration. Secrets and generated runtime files remain outside version control.

The target platform is Windows with Docker Desktop, NVIDIA driver `591.74`, GTX 1660 Ti with 6 GB VRAM, Python 3.11 in Conda environment `rag-local`, and the repository's existing Node/npm toolchain.
