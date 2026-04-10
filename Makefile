.PHONY: install up ingest api cli test fe-install fe-dev fe-build quality-gate benchmark apply-rollback

install:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .

up:
	docker compose up -d neo4j

ingest:
	python scripts/ingest.py

api:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"

cli:
	python scripts/query_cli.py "请总结系统架构"

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
