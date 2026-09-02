#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENT="production"
PROFILE="balanced"
MONITORING=false
WITH_N8N=false

usage() {
  cat <<'EOF'
Usage: ./deploy/scripts/deploy.sh [environment] [profile] [--monitoring] [--with-n8n]

Examples:
  ./deploy/scripts/deploy.sh production balanced
  ./deploy/scripts/deploy.sh development fast
  ./deploy/scripts/deploy.sh production balanced --monitoring --with-n8n
EOF
}

for arg in "$@"; do
  case "$arg" in
    --monitoring) MONITORING=true ;;
    --with-n8n) WITH_N8N=true ;;
    --help|-h) usage; exit 0 ;;
    development|test|production) ENVIRONMENT="$arg" ;;
    fast|balanced|deep) PROFILE="$arg" ;;
    *) echo "Unknown argument: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
command -v conda >/dev/null || { echo "Conda is required; activate or install rag-local." >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose is required." >&2; exit 1; }

RUNTIME_ENV="$ROOT/.runtime/${ENVIRONMENT}.env"
SECRETS_FILE="$ROOT/.runtime/generated-secrets.env"
conda run --no-capture-output -n rag-local python "$ROOT/deploy/scripts/config.py" render \
  --environment "$ENVIRONMENT" --profile "$PROFILE" --output "$RUNTIME_ENV"
[[ -f "$SECRETS_FILE" ]] || { echo "Generated secret file was not created." >&2; exit 1; }

COMPOSE_ARGS=(--project-directory "$ROOT" --project-name querymind --env-file "$RUNTIME_ENV" \
  -f "$ROOT/deploy/compose/compose.yaml")
if [[ "$ENVIRONMENT" == "development" ]]; then
  COMPOSE_ARGS+=(-f "$ROOT/deploy/compose/compose.dev.yaml")
fi
if [[ "$ENVIRONMENT" != "development" ]]; then
  COMPOSE_ARGS+=(-f "$ROOT/deploy/compose/compose.production.yaml")
fi
if [[ "$MONITORING" == true ]]; then
  COMPOSE_ARGS+=(-f "$ROOT/deploy/compose/compose.monitoring.yaml")
fi
if [[ "$WITH_N8N" == true ]]; then
  COMPOSE_ARGS+=(--profile with-n8n)
fi

export RUNTIME_ENV_FILE="$RUNTIME_ENV"
docker compose "${COMPOSE_ARGS[@]}" config -q
docker compose "${COMPOSE_ARGS[@]}" up -d --build
docker compose "${COMPOSE_ARGS[@]}" run --rm backend python deploy/scripts/init_app.py
docker compose "${COMPOSE_ARGS[@]}" exec -T backend python deploy/scripts/healthcheck.py \
  --port 8000

echo "QueryMind deployed: environment=$ENVIRONMENT profile=$PROFILE"
if [[ "$ENVIRONMENT" == "development" ]]; then
  echo "Frontend: http://127.0.0.1:5173"
else
  echo "Frontend: http://127.0.0.1"
fi
