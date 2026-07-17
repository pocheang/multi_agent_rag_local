.PHONY: install up ingest api cli test fe-install fe-dev fe-build quality-gate benchmark apply-rollback config-check config-render deploy deploy-dev deploy-monitoring

install:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .

up:
	docker compose up -d neo4j

ingest:
	python scripts/ingest.py

api:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"

cli:
	python scripts/query_cli.py "???????"

test:
	pytest -q

fe-install:
	cd frontend && npm install

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

quality-gate:
	python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md artifacts/quality-report.md

benchmark:
	python scripts/benchmark_pipeline.py --queries data/eval/benchmark_queries.txt

apply-rollback:
	python scripts/apply_rollback_profile.py --profile artifacts/rollback.env --env-file .env

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
