#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

. .venv/bin/activate
pip install -U pip
pip install -e .

docker compose up -d neo4j

echo "[INFO] If using Ollama, ensure these models are present:"
echo "  ollama pull qwen2.5:7b-instruct"
echo "  ollama pull nomic-embed-text"
echo "[INFO] Then run: python scripts/ingest.py"
echo "[INFO] Then run: uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload"
