.PHONY: install up ingest api cli test fe-install fe-dev fe-build

install:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .

up:
	docker compose up -d neo4j

ingest:
	python scripts/ingest.py

api:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

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
