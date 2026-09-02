# Local Core Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run QueryMind locally on Windows with Ollama, PostgreSQL, Redis, and Neo4j in Docker while FastAPI and Vite run on the host.

**Architecture:** A dedicated infrastructure-only Compose project exposes stateful services on loopback ports and persists them in named volumes. A tested Python lifecycle controller, invoked by a thin PowerShell wrapper, renders canonical configuration, starts and checks infrastructure, launches host processes, records their identities safely, and stops only the resources it owns.

**Tech Stack:** Python 3.11 (`rag-local` Conda), Docker Compose, Ollama 0.32.5, PostgreSQL 16.4, Redis 7.4.1, Neo4j 5.26.3, FastAPI/Uvicorn, React 18, Vite 6, Vitest 3, PowerShell.

## Global Constraints

- All Python operations use the Conda environment `rag-local`.
- The target host is Windows with Docker Desktop, NVIDIA driver `591.74`, and a GTX 1660 Ti with 6 GB VRAM.
- Docker owns only Ollama, PostgreSQL, Redis, and Neo4j; FastAPI and Vite run on the host.
- The default models are `qwen2.5:7b-instruct` and `nomic-embed-text`; `qwen2.5:3b-instruct` is the documented low-memory override.
- The backend remains on `127.0.0.1:8000`; the frontend remains on `127.0.0.1:5173`.
- All query execution continues to enter through `app.pipeline.rag_pipeline.RAGPipeline`.
- n8n, Prometheus, Grafana, Alertmanager, production TLS, and production hosting remain out of scope.
- Existing uncommitted changes are user-owned. Never reset, overwrite wholesale, or stage unrelated changes; inspect each touched file's current diff before editing.
- Normal start and stop operations must preserve Docker volumes, local databases, Chroma data, and downloaded models.
- Generated secrets and `.runtime/*.env` files remain ignored and must never be printed or committed.

---

### Task 1: Restore canonical local configuration

**Files:**
- Create: `config/env/base.env`
- Modify: `config/env/development.env.example`
- Create: `config/profiles/fast.env`
- Create: `config/profiles/balanced.env`
- Create: `config/profiles/deep.env`
- Modify: `deploy/scripts/config.py`
- Modify: `tests/test_config_generation.py`
- Existing test: `tests/test_deploy_assets.py`

**Interfaces:**
- Consumes: `deploy.scripts.config.merge_env_files()` and `render_environment()`.
- Produces: a development runtime with `MODEL_BACKEND=ollama`, host-published service URLs, expanded generated-secret references, pinned/default model names, and a selectable retrieval profile.

- [ ] **Step 1: Add a failing repository-layer behavior test**

Add `ROOT = Path(__file__).resolve().parents[1]` and this test to `tests/test_config_generation.py`:

```python
def test_canonical_development_layers_target_host_docker_services():
    values = merge_env_files(
        (
            ROOT / "config" / "env" / "base.env",
            ROOT / "config" / "env" / "development.env.example",
            ROOT / "config" / "profiles" / "balanced.env",
        )
    )

    assert values["MODEL_BACKEND"] == "ollama"
    assert values["OLLAMA_BASE_URL"] == "http://127.0.0.1:11434"
    assert values["OLLAMA_CHAT_MODEL"] == "qwen2.5:7b-instruct"
    assert values["OLLAMA_EMBED_MODEL"] == "nomic-embed-text"
    assert values["NEO4J_URI"] == "bolt://127.0.0.1:7687"
    assert values["REDIS_URL"] == "redis://:${REDIS_PASSWORD}@127.0.0.1:6379/0"
    assert values["RETRIEVAL_PROFILE"] == "advanced"


def test_render_environment_expands_generated_secret_references(tmp_path):
    root = tmp_path / "repo"
    (root / "config" / "env").mkdir(parents=True)
    (root / "config" / "profiles").mkdir(parents=True)
    (root / ".runtime").mkdir()
    write_env(
        root / "config" / "env" / "base.env",
        "MODEL_BACKEND=ollama\nREDIS_URL=redis://:${REDIS_PASSWORD}@127.0.0.1:6379/0\n",
    )
    write_env(root / "config" / "env" / "development.env.example", "APP_ENV=development\n")
    write_env(root / "config" / "profiles" / "balanced.env", "RETRIEVAL_PROFILE=advanced\n")
    write_env(
        root / ".runtime" / "generated-secrets.env",
        "POSTGRES_PASSWORD=postgres-secret\n"
        "NEO4J_PASSWORD=neo4j-secret\n"
        "REDIS_PASSWORD=redis-secret\n"
        "JWT_SECRET_KEY=jwt-secret\n"
        "API_SETTINGS_ENCRYPTION_KEY=encryption-secret\n"
        "ADMIN_CREATE_APPROVAL_TOKEN=approval-secret\n",
    )

    values = render_environment(
        "development", "balanced", tmp_path / "rendered.env", root
    )

    assert values["REDIS_URL"] == "redis://:redis-secret@127.0.0.1:6379/0"
```

- [ ] **Step 2: Run the configuration tests and verify the expected failure**

Run:

```powershell
conda run -n rag-local python -m pytest tests/test_config_generation.py tests/test_deploy_assets.py -v
```

Expected: failure because `config/env/base.env` and `config/profiles/*.env` do not exist.

- [ ] **Step 3: Create the shared and development layers**

Create `config/env/base.env` with shared safe defaults:

```dotenv
APP_ENV=development
MODEL_BACKEND=ollama
REASONING_MODEL_BACKEND=
OLLAMA_IMAGE=ollama/ollama:0.32.5
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_REASONING_MODEL=qwen2.5:7b-instruct
POSTGRES_DB=querymind
POSTGRES_USER=querymind
CHROMA_COLLECTION=local_rag_collection
CHROMA_PERSIST_DIR=./data/chroma
DATA_DIR=./data/docs
CORPUS_STORE_PATH=./data/chunks/chunks.jsonl
PARENT_STORE_PATH=./data/chunks/parents.jsonl
AUTO_INGEST_ENABLED=false
RETRIEVAL_CACHE_BACKEND=redis
QUERY_GUARD_BACKEND=redis
QUERY_RESULT_CACHE_BACKEND=redis
```

Keep the existing development values and add these exact overrides to `config/env/development.env.example`:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_REASONING_MODEL=qwen2.5:7b-instruct
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USERNAME=neo4j
REDIS_URL=redis://:${REDIS_PASSWORD}@127.0.0.1:6379/0
```

- [ ] **Step 4: Create the three strategy profiles**

Create `config/profiles/fast.env`:

```dotenv
RETRIEVAL_PROFILE=baseline
QUERY_REWRITE_ENABLED=false
QUERY_DECOMPOSE_ENABLED=false
RANK_FEATURE_ENABLED=false
DYNAMIC_RETRIEVAL_ENABLED=false
SYNTHESIS_REFINE_MAX_ROUNDS=1
QUERY_REQUEST_TIMEOUT_MS=12000
QUERY_MAX_CONCURRENT=32
QUERY_MAX_WAITING=160
QUERY_RETRY_MAX_ATTEMPTS=1
```

Create `config/profiles/balanced.env`:

```dotenv
RETRIEVAL_PROFILE=advanced
QUERY_REWRITE_ENABLED=true
QUERY_DECOMPOSE_ENABLED=true
RANK_FEATURE_ENABLED=true
DYNAMIC_RETRIEVAL_ENABLED=true
SYNTHESIS_REFINE_MAX_ROUNDS=3
QUERY_REQUEST_TIMEOUT_MS=60000
QUERY_MAX_CONCURRENT=24
QUERY_MAX_WAITING=120
QUERY_RETRY_MAX_ATTEMPTS=2
```

Create `config/profiles/deep.env`:

```dotenv
RETRIEVAL_PROFILE=safe
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_WITH_LLM=true
QUERY_DECOMPOSE_ENABLED=true
RANK_FEATURE_ENABLED=true
DYNAMIC_RETRIEVAL_ENABLED=true
SYNTHESIS_REFINE_MAX_ROUNDS=6
QUERY_REQUEST_TIMEOUT_MS=120000
QUERY_MAX_CONCURRENT=12
QUERY_MAX_WAITING=80
QUERY_RETRY_MAX_ATTEMPTS=3
```

- [ ] **Step 5: Expand generated-secret references during rendering**

Add this helper to `deploy/scripts/config.py`:

```python
REFERENCE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand_references(values: Mapping[str, str]) -> dict[str, str]:
    """Expand ${KEY} references from the merged configuration without logging values."""
    source = dict(values)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return source.get(key, match.group(0))

    return {key: REFERENCE_RE.sub(replace, value) for key, value in source.items()}
```

In `render_environment()`, call `values = expand_references(values)` after applying process overrides and before validation/writing. This ensures the host backend receives a usable authenticated Redis URL while the source-controlled layer contains no secret.

- [ ] **Step 6: Run the focused tests and render a real development file**

Run:

```powershell
conda run -n rag-local python -m pytest tests/test_config_generation.py tests/test_deploy_assets.py -v
conda run -n rag-local python deploy/scripts/config.py render --environment development --profile balanced --output .runtime/development.env
conda run -n rag-local python deploy/scripts/config.py validate --environment development --profile balanced
```

Expected: all tests pass; both configuration commands exit 0 without printing secret values.

- [ ] **Step 7: Check the task diff without staging user-owned changes**

Run `git diff --check -- config tests/test_config_generation.py`. Commit only newly created files if they can be isolated safely; leave pre-existing dirty files unstaged.

---

### Task 2: Add an infrastructure-only Docker Compose stack

**Files:**
- Create: `deploy/compose/compose.infrastructure.yaml`
- Create: `tests/test_local_infrastructure_compose.py`

**Interfaces:**
- Consumes: `.runtime/development.env` keys generated in Task 1.
- Produces: Compose services named `postgres`, `redis`, `neo4j`, `ollama`, and `ollama-init`, under project name `querymind-local`.

- [ ] **Step 1: Write a failing executable Compose contract test**

Create `tests/test_local_infrastructure_compose.py`:

```python
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "compose" / "compose.infrastructure.yaml"


def test_local_infrastructure_compose_renders_only_core_services(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is required for the Compose contract")

    docker_config = tmp_path / "docker-config"
    docker_config.mkdir()
    env_file = tmp_path / "runtime.env"
    env_file.write_text(
        "POSTGRES_PASSWORD=postgres-secret\n"
        "NEO4J_PASSWORD=neo4j-secret\n"
        "REDIS_PASSWORD=redis-secret\n"
        "OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct\n"
        "OLLAMA_EMBED_MODEL=nomic-embed-text\n",
        encoding="utf-8",
    )
    env = {**os.environ, "DOCKER_CONFIG": str(docker_config)}
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", str(env_file),
            "-f", str(COMPOSE), "config", "--format", "json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert set(config["services"]) == {"postgres", "redis", "neo4j", "ollama", "ollama-init"}
    assert config["services"]["ollama"]["image"] == "ollama/ollama:0.32.5"
    assert config["services"]["ollama"]["ports"][0]["published"] == "11434"
    assert config["services"]["ollama-init"]["depends_on"]["ollama"]["condition"] == "service_healthy"
```

- [ ] **Step 2: Run the test and verify it fails because the Compose file is absent**

Run:

```powershell
conda run -n rag-local python -m pytest tests/test_local_infrastructure_compose.py -v
```

Expected: failure identifying the missing Compose file.

- [ ] **Step 3: Create the pinned Compose stack**

Create `deploy/compose/compose.infrastructure.yaml` with:

```yaml
name: querymind-local

services:
  postgres:
    image: postgres:16.4-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-querymind}
      POSTGRES_USER: ${POSTGRES_USER:-querymind}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
    ports: ["127.0.0.1:5432:5432"]
    volumes: ["postgres_data:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER:-querymind}"]
      interval: 5s
      timeout: 5s
      retries: 20

  redis:
    image: redis:7.4.1-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD:?REDIS_PASSWORD is required}"]
    ports: ["127.0.0.1:6379:6379"]
    volumes: ["redis_data:/data"]
    healthcheck:
      test: ["CMD-SHELL", "redis-cli --no-auth-warning -a \"$${REDIS_PASSWORD}\" ping | grep PONG"]
      interval: 5s
      timeout: 5s
      retries: 20

  neo4j:
    image: neo4j:5.26.3
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_initial__size: 512m
      NEO4J_dbms_memory_heap_max__size: 2G
      NEO4J_dbms_memory_pagecache_size: 1G
    ports: ["127.0.0.1:7474:7474", "127.0.0.1:7687:7687"]
    volumes: ["neo4j_data:/data", "neo4j_logs:/logs", "neo4j_plugins:/plugins"]
    healthcheck:
      test: ["CMD-SHELL", "wget --quiet --tries=1 --spider http://localhost:7474 || exit 1"]
      interval: 5s
      timeout: 10s
      retries: 30

  ollama:
    image: ${OLLAMA_IMAGE:-ollama/ollama:0.32.5}
    restart: unless-stopped
    gpus: all
    ports: ["127.0.0.1:11434:11434"]
    volumes: ["ollama_models:/root/.ollama"]
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 10s
      retries: 30

  ollama-init:
    image: ${OLLAMA_IMAGE:-ollama/ollama:0.32.5}
    restart: "no"
    environment:
      OLLAMA_HOST: http://ollama:11434
      OLLAMA_CHAT_MODEL: ${OLLAMA_CHAT_MODEL:-qwen2.5:7b-instruct}
      OLLAMA_EMBED_MODEL: ${OLLAMA_EMBED_MODEL:-nomic-embed-text}
    entrypoint: ["/bin/sh", "-c"]
    command: ['ollama pull "$${OLLAMA_CHAT_MODEL}" && ollama pull "$${OLLAMA_EMBED_MODEL}"']
    depends_on:
      ollama:
        condition: service_healthy

volumes:
  postgres_data:
  redis_data:
  neo4j_data:
  neo4j_logs:
  neo4j_plugins:
  ollama_models:
```

- [ ] **Step 4: Validate behavior and GPU syntax**

Run:

```powershell
conda run -n rag-local python -m pytest tests/test_local_infrastructure_compose.py -v
docker compose --project-name querymind-local --env-file .runtime/development.env -f deploy/compose/compose.infrastructure.yaml config -q
```

Expected: both commands exit 0 and Compose contains no backend, frontend, n8n, or monitoring service.

- [ ] **Step 5: Check the task diff**

Run `git diff --check -- deploy/compose/compose.infrastructure.yaml tests/test_local_infrastructure_compose.py`. These are new files and may be committed together if no unrelated path is staged.

---

### Task 3: Implement safe local lifecycle control

**Files:**
- Create: `deploy/scripts/local_dev.py`
- Create: `deploy/scripts/local-dev.ps1`
- Create: `tests/scripts/test_local_dev.py`

**Interfaces:**
- Produces: `ProcessRecord(name: str, pid: int, create_time: float)`.
- Produces: `compose_command(root: Path, runtime_env: Path) -> list[str]`.
- Produces: `listening_ports(ports: list[int], host: str = "127.0.0.1") -> list[int]`.
- Produces: `terminate_recorded_process(record: ProcessRecord) -> bool`.
- Produces CLI: `python deploy/scripts/local_dev.py {start|status|stop} --profile balanced`.
- Persists: `.runtime/local-dev-processes.json` containing only process name, PID, and creation time.

- [ ] **Step 1: Write failing process ownership and command tests**

Create `tests/scripts/test_local_dev.py`:

```python
import subprocess
import socket
import sys

import psutil

from deploy.scripts.local_dev import (
    ProcessRecord,
    compose_command,
    listening_ports,
    terminate_recorded_process,
)


def test_compose_command_uses_infrastructure_file_and_local_project(tmp_path):
    command = compose_command(tmp_path, tmp_path / ".runtime" / "development.env")
    assert command == [
        "docker", "compose",
        "--project-directory", str(tmp_path),
        "--project-name", "querymind-local",
        "--env-file", str(tmp_path / ".runtime" / "development.env"),
        "-f", str(tmp_path / "deploy" / "compose" / "compose.infrastructure.yaml"),
    ]


def test_listening_ports_reports_only_bound_ports():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        bound_port = listener.getsockname()[1]
        assert listening_ports([bound_port]) == [bound_port]


def test_terminate_recorded_process_refuses_reused_pid():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        actual = psutil.Process(process.pid)
        wrong = ProcessRecord("dummy", process.pid, actual.create_time() + 60)
        assert terminate_recorded_process(wrong) is False
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_terminate_recorded_process_stops_matching_process():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    actual = psutil.Process(process.pid)
    record = ProcessRecord("dummy", process.pid, actual.create_time())
    assert terminate_recorded_process(record) is True
    process.wait(timeout=10)
    assert process.returncode is not None
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run:

```powershell
conda run -n rag-local python -m pytest tests/scripts/test_local_dev.py -v
```

Expected: collection fails because `deploy.scripts.local_dev` does not exist.

- [ ] **Step 3: Implement the tested process and Compose primitives**

Create `deploy/scripts/local_dev.py` with these exact public contracts:

```python
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil

from deploy.scripts.config import parse_env_file, render_environment


@dataclass(frozen=True)
class ProcessRecord:
    name: str
    pid: int
    create_time: float


def compose_command(root: Path, runtime_env: Path) -> list[str]:
    return [
        "docker", "compose",
        "--project-directory", str(root),
        "--project-name", "querymind-local",
        "--env-file", str(runtime_env),
        "-f", str(root / "deploy" / "compose" / "compose.infrastructure.yaml"),
    ]


def listening_ports(ports: list[int], host: str = "127.0.0.1") -> list[int]:
    occupied: list[int] = []
    for port in ports:
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex((host, port)) == 0:
                occupied.append(port)
    return occupied


def terminate_recorded_process(record: ProcessRecord) -> bool:
    try:
        process = psutil.Process(record.pid)
    except psutil.NoSuchProcess:
        return False
    if abs(process.create_time() - record.create_time) > 0.01:
        return False
    descendants = process.children(recursive=True)
    for child in reversed(descendants):
        child.terminate()
    process.terminate()
    _, alive = psutil.wait_procs([*descendants, process], timeout=10)
    for remaining in alive:
        remaining.kill()
    return True
```

Implement private helpers with these exact behaviors:

- `_require_command(name)` uses `shutil.which` and raises `RuntimeError("Required command not found: <name>")`.
- `_run(argv, cwd, env=None)` uses `subprocess.run(..., check=True)` without shell interpolation.
- `_wait_for_url(url, timeout)` polls with `urllib.request.urlopen` every 0.5 seconds until an HTTP response arrives or raises `RuntimeError("Timed out waiting for <url>")`.
- `_save_manifest(path, records)` writes `asdict(record)` JSON atomically through a sibling `.tmp` file.
- `_load_manifest(path)` returns `ProcessRecord` objects and returns an empty list when the file is absent.
- `_start_process(...)` redirects stdout/stderr to `.runtime/<name>.log` and `.runtime/<name>.err.log`, starts a new process without opening a visible console, and captures `psutil.Process(pid).create_time()`.

Implement actions exactly as follows:

- `start`: check `docker`, `node`, and `npm`; refuse to replace live processes already present in the manifest; require host ports 8000 and 5173 to be free; render `.runtime/development.env`; run Compose `up -d postgres redis neo4j ollama`; run Compose `run --rm ollama-init`; run `deploy/scripts/init_app.py`; launch Uvicorn with `sys.executable`; launch Vite with `node frontend/node_modules/vite/bin/vite.js --config vite.config.mjs --configLoader runner`; pass the parsed runtime values plus `RUNTIME_ENV_FILE=<absolute runtime path>` to both host processes; save the manifest; wait for backend `/health` and frontend `/`.
- `status`: report Compose `ps`, validate recorded process identities, check Ollama `/api/tags`, backend `/health` and `/ready`, and frontend `/`; return nonzero if any required component is unavailable.
- `stop`: terminate only matching recorded processes, remove the manifest, and run Compose `down` without `--volumes` or `-v`.
- `main(argv=None)`: accept `start`, `status`, or `stop`, plus `--profile {fast,balanced,deep}`; catch expected runtime/subprocess errors, print one concise message to stderr, and return 1.

- [ ] **Step 4: Add the PowerShell entry point**

Create `deploy/scripts/local-dev.ps1`:

```powershell
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "status", "stop")]
    [string]$Action = "start",
    [ValidateSet("fast", "balanced", "deep")]
    [string]$Profile = "balanced"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    throw "Conda is required and environment 'rag-local' must exist."
}

conda run --no-capture-output -n rag-local python `
    (Join-Path $Root "deploy/scripts/local_dev.py") $Action --profile $Profile
exit $LASTEXITCODE
```

- [ ] **Step 5: Run focused lifecycle tests**

Run:

```powershell
conda run -n rag-local python -m pytest tests/scripts/test_local_dev.py -v
```

Expected: all tests pass, including the real PID ownership checks.

- [ ] **Step 6: Check safety invariants in the real command plan**

Run:

```powershell
rg -n "down -v|down --volumes|Stop-Process.*python|Stop-Process.*node|taskkill" deploy/scripts/local_dev.py deploy/scripts/local-dev.ps1
```

Expected: no matches. Run `git diff --check` on the three task files before staging any new files.

---

### Task 4: Restore legacy agent compatibility exports

**Files:**
- Modify: `app/agents/quality_orchestrator_agent.py`
- Modify: `app/agents/retrieval_quality_agent.py`
- Modify: `app/agents/graph_rag_agent.py`
- Modify: `app/agents/synthesis_agent.py`
- Modify: `app/agents/web_research_agent.py`
- Existing tests: `tests/agents/test_quality_orchestrator.py`
- Existing tests: `tests/agents/test_retrieval_quality.py`
- Existing tests: `tests/graph/test_critical_fixes.py`
- Existing tests: `tests/test_graph_rag_optimization.py`
- Existing tests: `tests/unit/test_synthesis_language.py`
- Existing tests: `tests/unit/test_web_research_agent.py`

**Interfaces:**
- Consumes: canonical implementations under `app.agents.validation`, `app.agents.rag`, and `app.agents.synthesizer`.
- Produces: identity-preserving legacy imports for functions still imported by production/tests.

- [ ] **Step 1: Re-run the focused imports and record the red state**

Run:

```powershell
conda run -n rag-local python -m pytest tests/agents/test_quality_orchestrator.py tests/agents/test_retrieval_quality.py tests/graph/test_critical_fixes.py tests/test_graph_rag_optimization.py tests/unit/test_synthesis_language.py tests/unit/test_web_research_agent.py --collect-only -q
```

Expected: six import errors naming missing compatibility exports.

- [ ] **Step 2: Re-export the exact canonical symbols**

Add these imports and names to each shim's `__all__`:

```python
# app/agents/quality_orchestrator_agent.py
from app.agents.validation.quality_orchestrator import _classify_quality_level, orchestrate_quality

# app/agents/retrieval_quality_agent.py
from app.agents.rag.retrieval_quality import (
    LLM_SCORING_AVAILABLE,
    _calculate_completeness_score,
    _calculate_coverage_score,
    _calculate_diversity_score,
    _calculate_relevance_score,
    evaluate_retrieval_quality,
)

# app/agents/graph_rag_agent.py
from app.agents.rag.graph import _format_graph_context, _run_basic_graph_rag, run_graph_rag

# app/agents/synthesis_agent.py
from app.agents.synthesizer.generation import _build_prompt_with_language

# app/agents/web_research_agent.py
from app.agents.rag.web import _parse_allowlist, _sanitize_query, _source_score, run_web_research
```

Do not duplicate implementations in compatibility modules.

- [ ] **Step 3: Verify imports and focused behavior**

Run the six test files without `--collect-only`:

```powershell
conda run -n rag-local python -m pytest tests/agents/test_quality_orchestrator.py tests/agents/test_retrieval_quality.py tests/graph/test_critical_fixes.py tests/test_graph_rag_optimization.py tests/unit/test_synthesis_language.py tests/unit/test_web_research_agent.py -v
```

Expected: collection succeeds; address only failures directly caused by the export boundary in this task.

- [ ] **Step 4: Inspect without committing pre-existing refactor content**

Run `git diff --check` for the five shim paths. These files were already modified before this task, so do not stage them as a blanket commit.

---

### Task 5: Remove the graph import cycle and repair chart extraction ownership

**Files:**
- Modify: `app/graph/execution/__init__.py`
- Modify: `app/ingestion/extraction/charts_batch.py`
- Existing test: `tests/integration/test_session_language_tracking.py`
- Existing test: `tests/test_batch_chart_extractor.py`
- Existing test: `tests/integration/test_batch_chart_extraction.py`

**Interfaces:**
- Produces: eager `GraphState` import and lazy package-level access to `build_workflow`, `clear_workflow_cache`, `run_query`, and `get_graph`.
- Consumes: `extract_chart_data_with_vision` from `app.ingestion.extraction.charts`.

- [ ] **Step 1: Verify the two independent red failures**

Run:

```powershell
conda run -n rag-local python -m pytest tests/integration/test_session_language_tracking.py tests/test_batch_chart_extractor.py tests/integration/test_batch_chart_extraction.py --collect-only -q
```

Expected: one circular import through `app.graph.execution.__init__` and one missing `app.ingestion.extraction.chart_extractor` module.

- [ ] **Step 2: Make graph workflow exports lazy**

Replace the eager workflow/studio imports in `app/graph/execution/__init__.py` with:

```python
"""Graph state, workflow construction, and Studio entry points."""

from app.graph.execution.state import GraphState

__all__ = ["GraphState", "build_workflow", "clear_workflow_cache", "get_graph", "run_query"]


def __getattr__(name: str):
    if name == "get_graph":
        from app.graph.execution.studio_entry import get_graph

        return get_graph
    if name in {"build_workflow", "clear_workflow_cache", "run_query"}:
        from app.graph.execution.workflow import build_workflow, clear_workflow_cache, run_query

        return {
            "build_workflow": build_workflow,
            "clear_workflow_cache": clear_workflow_cache,
            "run_query": run_query,
        }[name]
    raise AttributeError(name)
```

- [ ] **Step 3: Point batch extraction at its canonical sibling**

Change the import in `app/ingestion/extraction/charts_batch.py` to:

```python
from .charts import extract_chart_data_with_vision
```

- [ ] **Step 4: Run the focused test files**

Run:

```powershell
conda run -n rag-local python -m pytest tests/integration/test_session_language_tracking.py tests/test_batch_chart_extractor.py tests/integration/test_batch_chart_extraction.py -v
```

Expected: all three files collect; the circular import and missing module failures are absent.

- [ ] **Step 5: Re-run complete backend collection**

Run:

```powershell
conda run -n rag-local python -m pytest --collect-only -q
```

Expected: all backend tests collect with zero errors. Inspect the two file diffs without staging unrelated verticalization work.

---

### Task 6: Make Vite and Vitest use the Windows-safe config loader

**Files:**
- Modify: `frontend/package.json`
- Verify: `frontend/package-lock.json`

**Interfaces:**
- Produces npm scripts that load `vite.config.mjs` and `vitest.config.ts` with Vite's `runner` config loader.

- [ ] **Step 1: Capture the red frontend commands**

Run:

```powershell
conda run -n rag-local npm test -- --run
conda run -n rag-local npm run build
```

from `frontend/`.

Expected: both commands fail while the default bundled config loader attempts to read outside the workspace.

- [ ] **Step 2: Change only the npm command boundary**

Set the scripts in `frontend/package.json` to:

```json
{
  "dev": "vite --config vite.config.mjs --configLoader runner",
  "test": "vitest --config vitest.config.ts --configLoader runner",
  "build": "tsc -b && vite build --config vite.config.mjs --configLoader runner"
}
```

Leave dependency versions unchanged. Confirm `frontend/package-lock.json` does not change because npm scripts are not lockfile dependency data.

- [ ] **Step 3: Run tests and production build**

Run from `frontend/`:

```powershell
conda run -n rag-local npm test -- --run
conda run -n rag-local npm run build
```

Expected: Vitest reports zero failed tests; TypeScript and Vite exit 0.

- [ ] **Step 4: Smoke-test the development command**

Start `npm run dev -- --host 127.0.0.1 --port 5173`, poll `http://127.0.0.1:5173/`, then terminate only that recorded process. Expected: HTTP 200 and no config-loader error.

- [ ] **Step 5: Inspect the existing frontend diff**

Run `git diff --check -- frontend/package.json frontend/package-lock.json`. `package.json` was already user-modified, so do not stage it as a blanket commit.

---

### Task 7: Document and verify the complete core runtime

**Files:**
- Modify: `README.md`
- Modify: `docs/getting-started/setup.md`
- Modify: `deploy/README.md`

**Interfaces:**
- Documents: `deploy/scripts/local-dev.ps1 start|status|stop` and model override through `OLLAMA_CHAT_MODEL`.
- Verifies: infrastructure health, Ollama chat/embed, backend health/readiness, frontend response/proxy, and data-preserving restart.

- [ ] **Step 1: Add the canonical Windows workflow to documentation**

Document these exact commands in all relevant entry points, with `README.md` linking to the full setup guide:

```powershell
# Start Docker infrastructure and host backend/frontend
powershell -ExecutionPolicy Bypass -File deploy/scripts/local-dev.ps1 start -Profile balanced

# Inspect every required component
powershell -ExecutionPolicy Bypass -File deploy/scripts/local-dev.ps1 status

# Stop owned host processes and project containers; keep all volumes
powershell -ExecutionPolicy Bypass -File deploy/scripts/local-dev.ps1 stop
```

Document the low-memory override before `start`:

```powershell
$env:OLLAMA_CHAT_MODEL = "qwen2.5:3b-instruct"
```

Explicitly state that `stop` preserves named volumes and that the first start downloads approximately 5 GB of model data.

- [ ] **Step 2: Run backend static and test verification**

Run from the repository root:

```powershell
conda run -n rag-local ruff check app deploy/scripts tests
conda run -n rag-local python -m pytest --collect-only -q
conda run -n rag-local python -m pytest tests/test_config_generation.py tests/test_deploy_assets.py tests/test_local_infrastructure_compose.py tests/scripts/test_local_dev.py -v
```

Then run the full suite:

```powershell
conda run -n rag-local python -m pytest tests/ -v
```

Expected: zero collection errors. If the full suite has failures unrelated to this runtime work, record the exact failing tests and evidence; do not hide them or broaden changes without a root-cause analysis.

- [ ] **Step 3: Run frontend verification**

Run from `frontend/`:

```powershell
conda run -n rag-local npm test -- --run
conda run -n rag-local npm run build
```

Expected: both commands exit 0.

- [ ] **Step 4: Start the complete local core runtime**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/scripts/local-dev.ps1 start -Profile balanced
powershell -ExecutionPolicy Bypass -File deploy/scripts/local-dev.ps1 status
```

Expected: PostgreSQL, Redis, Neo4j, and Ollama are healthy; backend `/health` and `/ready` succeed; frontend `/` succeeds.

- [ ] **Step 5: Verify Ollama generation and embeddings**

Run:

```powershell
$chat = @{model="qwen2.5:7b-instruct"; messages=@(@{role="user"; content="Reply with OK"}); stream=$false} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/chat -ContentType application/json -Body $chat
$embed = @{model="nomic-embed-text"; input="QueryMind health check"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/embed -ContentType application/json -Body $embed
```

Expected: the chat response contains a non-empty message and the embed response contains a non-empty embeddings array.

- [ ] **Step 6: Verify the browser-to-backend path**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/ready
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/
```

Also request a proxied backend route through port 5173 using a route present in the final FastAPI route table. Expected: the response reaches FastAPI rather than returning Vite HTML.

- [ ] **Step 7: Verify data-preserving restart**

Capture `docker volume ls --filter label=com.docker.compose.project=querymind-local`, run `local-dev.ps1 stop`, then `start` and `status` again. Expected: the same named volumes remain and Ollama does not re-download models already present.

- [ ] **Step 8: Final diff and requirement review**

Run `git diff --check`, inspect `git status --short`, compare every design requirement with this plan, and report:

- exact files changed;
- focused/full test counts and failures;
- frontend test/build results;
- container health;
- Ollama chat/embed evidence;
- backend/frontend URLs;
- any remaining limitation tied to missing user documents rather than runtime readiness.

Do not claim completion unless these commands were run freshly and their exit codes/output support the claim.

## References

- Ollama Docker and NVIDIA GPU setup: <https://docs.ollama.com/docker>
- Ollama GPU support requirements: <https://docs.ollama.com/gpu>
- Pinned Ollama image tag: <https://hub.docker.com/r/ollama/ollama/tags>
- Qwen 2.5 7B model: <https://ollama.com/library/qwen2.5:7b-instruct>
- Nomic embedding model: <https://ollama.com/library/nomic-embed-text>
