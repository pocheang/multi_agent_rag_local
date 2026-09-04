.PHONY: install up down api test lint eval-retrieval lock fe-install fe-dev fe-build config-check config-render deploy deploy-dev deploy-monitoring

install:
	conda run -n rag-local pip install -e ".[dev]"
	conda run -n rag-local pre-commit install

# Start the optional graph database for local development.
#
# `docker compose up -d neo4j` on its own could never work: there is no compose
# file in the repository root, so it exited with "no configuration file
# provided". The stack lives under deploy/compose/, compose.yaml requires
# NEO4J_PASSWORD (declared with :? so it is mandatory), and the dev overlay is
# what publishes 7474/7687 to 127.0.0.1 -- a locally run uvicorn is not on the
# compose network, so without it NEO4J_URI's bolt://localhost:7687 reaches
# nothing. Mirrors how deploy/scripts/deploy.sh invokes compose.
# No --project-directory: compose then resolves the files' relative paths
# against deploy/compose/, which is what `env_file: ../../.runtime/...` and the
# `../../app` bind mounts are written for. Passing the repo root instead sent
# both two levels too high (verified: it looked for .runtime/ beside the repo).
# RUNTIME_ENV_FILE overrides that env_file default, which points at
# production.env -- absent on a development checkout.
COMPOSE_DEV = RUNTIME_ENV_FILE=../../.runtime/development.env docker compose --project-name querymind --env-file .runtime/development.env -f deploy/compose/compose.yaml -f deploy/compose/compose.dev.yaml

up:
	@test -f .runtime/development.env || { echo "Missing .runtime/development.env -- run: make config-render ENV=development" >&2; exit 1; }
	$(COMPOSE_DEV) up -d neo4j
	@echo "Neo4j Browser: http://localhost:7474 (user neo4j, password in .runtime/development.env)"

down:
	$(COMPOSE_DEV) down

api:
	conda run --no-capture-output -n rag-local uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"

# Retrieval quality over the corpus that ships in config/eval/. BM25 only, so it
# needs no embedding model, no Chroma and no LLM. Deliberately not a CI gate for
# the vector path -- see the docstring in scripts/eval_retrieval.py.
eval-retrieval:
	conda run --no-capture-output -n rag-local python scripts/eval_retrieval.py

fe-install:
	cd frontend && npm ci

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

# uv.lock is the lock; requirements/*.txt are exports of it for pip, which
# cannot read uv.lock. One resolution, so the three cannot disagree -- they used
# to be two independent `uv pip compile` runs, which could. Takes minutes: the
# hashes come from the real archives. Needs `uv` (pip install uv).
lock:
	uv lock
	uv export --frozen --no-emit-project --no-dev --no-annotate --no-header -o requirements/runtime.txt
	uv export --frozen --no-emit-project --extra dev --no-annotate --no-header -o requirements/ci.txt
	conda run --no-capture-output -n rag-local python scripts/check_lock_wheels.py

test:
	conda run --no-capture-output -n rag-local pytest -q

lint:
	conda run --no-capture-output -n rag-local ruff check .
	conda run --no-capture-output -n rag-local ruff format --check .

# ingest/cli/quality-gate/benchmark/refactor-inventory/apply-rollback targets removed
# 2026-08-28: relied on scripts/, cleared ahead of the v0.7 rewrite. `test` and `lint`
# came back on 2026-08-29 when tests/ and CI were rebuilt.

ENV ?= production
PROFILE ?= balanced

config-check:
	conda run -n rag-local python deploy/scripts/config.py validate --environment $(ENV) --profile $(PROFILE)

config-render:
	conda run -n rag-local python deploy/scripts/config.py render --environment $(ENV) --profile $(PROFILE) --output .runtime/$(ENV).env

deploy:
	./deploy/scripts/deploy.sh $(ENV) $(PROFILE)

deploy-dev:
	./deploy/scripts/deploy.sh development $(PROFILE)

deploy-monitoring:
	./deploy/scripts/deploy.sh $(ENV) $(PROFILE) --monitoring
