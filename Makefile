.PHONY: install up api test lint lock fe-install fe-dev fe-build config-check config-render deploy deploy-dev deploy-monitoring

install:
	conda run -n rag-local pip install -e ".[dev]"
	conda run -n rag-local pre-commit install

up:
	docker compose up -d neo4j

api:
	conda run --no-capture-output -n rag-local uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"

fe-install:
	cd frontend && npm ci

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

# Recompile the dependency locks CI and the image install from. Takes minutes:
# --generate-hashes fetches every archive to hash it. Compiled for the platform
# they are used on, not the one you run this from, so the result is the same
# whoever regenerates it. Needs `uv` (pip install uv).
lock:
	uv pip compile pyproject.toml --python-platform linux --python-version 3.11 --generate-hashes --no-annotate -o requirements/runtime.txt
	uv pip compile pyproject.toml --extra dev --python-platform linux --python-version 3.11 --generate-hashes --no-annotate -o requirements/ci.txt

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
