.PHONY: install up api fe-install fe-dev fe-build config-check config-render deploy deploy-dev deploy-monitoring

install:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .

up:
	docker compose up -d neo4j

api:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"

fe-install:
	cd frontend && npm install

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

# ingest/cli/test/quality-gate/benchmark/refactor-inventory/apply-rollback targets removed
# 2026-08-28: relied on scripts/ and tests/, both cleared ahead of the v0.7 rewrite.

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
