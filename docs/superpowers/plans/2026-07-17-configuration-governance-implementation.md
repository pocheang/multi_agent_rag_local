# QueryMind Configuration Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate QueryMind configuration into `config/`, deployment assets into `deploy/`, and provide repeatable one-command Docker Compose deployment for development and production.

**Architecture:** Keep application environment variables as the compatibility interface. A standard-library Python generator merges `config/env`, one runtime profile, generated local secrets, and explicit process overrides into `.runtime/<environment>.env`. Compose files live under `deploy/compose`; shell and PowerShell wrappers call the same generator, validate the rendered Compose model, start services, initialize the existing SQLite schema idempotently, and run health checks.

**Tech Stack:** Python 3.11 standard library, Pydantic Settings, FastAPI, Docker Compose v2, Bash, PowerShell, pytest, React/Vite.

## Global Constraints

- All Python commands run in the `rag-local` Conda environment.
- The existing environment variable names in `app/core/config.py` remain compatible.
- No SQLite-to-PostgreSQL application data migration is included.
- No real API keys, passwords, JWT secrets, encryption keys, or admin tokens are committed.
- `.runtime/` is generated locally and is never used as a source-controlled configuration directory.
- Production Compose does not publish PostgreSQL, Neo4j, Redis, Prometheus, Grafana, or Alertmanager management ports.
- No task may execute `docker compose down -v` or delete data volumes.
- Existing user changes in the worktree are unrelated input and must not be reverted or reformatted.
- Every task ends with its own focused test or validation command before the next task starts.

---

## File Map

### New files

- `config/README.md` — canonical configuration ownership, precedence, and editing rules.
- `config/env/base.env` — shared non-secret defaults.
- `config/env/development.env.example` — local Conda development overrides.
- `config/env/test.env.example` — isolated test overrides.
- `config/env/production.env.example` — production-safe non-secret template.
- `config/env/frontend/development.env.example` — Vite development variables.
- `config/env/frontend/production.env.example` — Vite production variables.
- `config/profiles/fast.env`, `config/profiles/balanced.env`, `config/profiles/deep.env` — runtime strategy overlays.
- `config/application/router_calibration.json` — migrated router calibration data.
- `config/application/web_activity_config.json` — migrated web activity configuration.
- `config/observability/**` — migrated monitoring configuration.
- `deploy/README.md` — deployment commands, ports, volumes, backup and rollback rules.
- `deploy/compose/compose.yaml` — production Compose baseline.
- `deploy/compose/compose.dev.yaml` — development Compose override.
- `deploy/compose/compose.monitoring.yaml` — optional monitoring override.
- `deploy/scripts/config.py` — environment parser, merger, validator, and secret generator.
- `deploy/scripts/healthcheck.py` — service readiness and endpoint checks.
- `deploy/scripts/init_app.py` — idempotent SQLite/auth schema initialization.
- `deploy/scripts/deploy.sh` — Linux/macOS one-command wrapper.
- `deploy/scripts/deploy.ps1` — Windows PowerShell one-command wrapper.
- `tests/test_config_generation.py` — configuration generator unit tests.
- `tests/test_deploy_assets.py` — Compose and deployment asset validation tests.

### Modified files

- `app/agents/router_calibration.py` — default calibration path moves under `config/application`.
- `Dockerfile` — copy `deploy/` into the backend image for initialization and health tooling.
- `Dockerfile.frontend` — use the production frontend env template during the build contract.
- `Makefile` — delegate `deploy`, `deploy-dev`, `deploy-monitoring`, `config-check`, and `config-init` to the canonical scripts.
- `.gitignore` — ignore `.runtime/` and generated deployment state.
- `README.md` — point quick start and deployment instructions to `config/` and `deploy/`.
- `docs/getting-started/configuration.md`, `docs/getting-started/quick-start.md`, `docs/operations/docker.md`, `docs/operations/deployment.md`, `docs/operations/quick-deploy.md`, `docs/reference/configuration.md`, `docs/reference/faq.md`, and current monitoring deployment docs — replace current-path commands with canonical commands.
- `tests/test_web_activity_system.py` — use `config/application/web_activity_config.json`.

### Retired or migrated files

- `.env.example`, `.env.docker.example`, `.env.docling.example`, `.env.optimized`, `.env.optimized.recommended`, `.env.security` — replace tracked templates with `config/env` templates; do not delete ignored local copies automatically.
- `configs/runtime-profiles/*.env` — move to `config/profiles/*.env`.
- `config/router_calibration.json`, `config/web_activity_config.json` — move into `config/application`.
- `config/prometheus`, `config/grafana`, `config/alertmanager` — move into `config/observability`.
- `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.monitoring.yml` — move to `deploy/compose` or leave compatibility wrappers that contain no independent service definitions.
- `start.sh`, `start.bat`, `restart.bat` — delegate to `deploy/scripts` if retained.

---

## Task 1: Create the canonical configuration tree

**Files:**
- Create: `config/README.md`, `config/env/base.env`, `config/env/development.env.example`, `config/env/test.env.example`, `config/env/production.env.example`
- Create: `config/env/frontend/development.env.example`, `config/env/frontend/production.env.example`
- Create: `config/profiles/fast.env`, `config/profiles/balanced.env`, `config/profiles/deep.env`
- Create: `config/application/router_calibration.json`, `config/application/web_activity_config.json`
- Create/Move: `config/observability/prometheus/*`, `config/observability/grafana/*`, `config/observability/alertmanager/*`
- Modify: `app/agents/router_calibration.py`, `tests/test_web_activity_system.py`, `.gitignore`
- Test: `tests/test_deploy_assets.py`

**Interfaces:**
- Produces exactly one canonical configuration root: `config/`.
- Produces profile files containing only runtime strategy keys.
- Keeps `app/agents/router_calibration.py` default path equal to `Path(repo_root) / "config" / "application" / "router_calibration.json"`.

- [ ] **Step 1: Write the asset-layout test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_configuration_layout_exists():
    expected = (
        ROOT / "config" / "env" / "base.env",
        ROOT / "config" / "env" / "development.env.example",
        ROOT / "config" / "env" / "test.env.example",
        ROOT / "config" / "env" / "production.env.example",
        ROOT / "config" / "profiles" / "fast.env",
        ROOT / "config" / "profiles" / "balanced.env",
        ROOT / "config" / "profiles" / "deep.env",
        ROOT / "config" / "application" / "router_calibration.json",
        ROOT / "config" / "application" / "web_activity_config.json",
        ROOT / "config" / "observability" / "prometheus" / "prometheus.yml",
        ROOT / "config" / "observability" / "grafana" / "datasources.yml",
        ROOT / "config" / "observability" / "alertmanager" / "alertmanager.yml",
    )
    missing = [str(path.relative_to(ROOT)) for path in expected if not path.is_file()]
    assert missing == []


def test_profiles_do_not_define_provider_secrets():
    forbidden = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "POSTGRES_PASSWORD", "NEO4J_PASSWORD", "REDIS_PASSWORD"}
    for profile in (ROOT / "config" / "profiles").glob("*.env"):
        names = {
            line.split("=", 1)[0].strip()
            for line in profile.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "=" in line
        }
        assert names.isdisjoint(forbidden), profile
```

- [ ] **Step 2: Run the layout test before migration**

Run: `conda run -n rag-local pytest tests/test_deploy_assets.py::test_canonical_configuration_layout_exists -q`

Expected: FAIL because the canonical directories do not yet exist.

- [ ] **Step 3: Populate the canonical files**

Copy the existing non-secret values into the new files with these rules:

```text
base.env                    = shared defaults from .env.example
development.env.example    = APP_ENV=development, DEBUG=true, localhost paths, AUTH_COOKIE_SECURE=false
test.env.example           = APP_ENV=test, isolated data paths under .tmp/test-runtime, memory caches
production.env.example     = APP_ENV=production, DEBUG=false, explicit CORS, secure cookies, no weak secrets
fast/balanced/deep.env     = only the values currently in configs/runtime-profiles/*.env
frontend/*.env.example     = VITE_API_BASE_URL only
```

Copy monitoring files without changing their rule semantics, then update the Prometheus/Grafana/Alertmanager mount paths in the new Compose file during Task 3.

- [ ] **Step 4: Update mutable router calibration path**

Change the existing constant in `app/agents/router_calibration.py` from:

```python
CALIBRATION_CONFIG_DIR: Final[Path] = Path(__file__).parent.parent.parent / "config"
```

to:

```python
CALIBRATION_CONFIG_DIR: Final[Path] = (
    Path(__file__).resolve().parents[2] / "config" / "application"
)
```

Keep `DEFAULT_CALIBRATION_FILE` unchanged. Update the web activity test fixture path to `config/application/web_activity_config.json`.

- [ ] **Step 5: Add `.runtime/` ignores and run the layout test**

Add these exact entries to `.gitignore`:

```gitignore
# Canonical deployment runtime output
.runtime/
deploy/.runtime/
```

Run: `conda run -n rag-local pytest tests/test_deploy_assets.py -q`

Expected: PASS for the layout and profile safety tests.

---

## Task 2: Implement configuration merge, validation, and secret generation

**Files:**
- Create: `deploy/scripts/config.py`
- Create: `tests/test_config_generation.py`

**Interfaces:**
- `parse_env_file(path: Path) -> dict[str, str]`
- `merge_env_files(paths: Iterable[Path], overrides: Mapping[str, str] | None = None) -> dict[str, str]`
- `generate_secrets(path: Path, existing: Mapping[str, str] | None = None) -> dict[str, str]`
- `validate_environment(values: Mapping[str, str], environment: str) -> list[str]`
- `render_environment(environment: str, profile: str, output: Path, repo_root: Path) -> dict[str, str]`
- CLI: `python deploy/scripts/config.py render --environment production --profile balanced --output .runtime/production.env`

- [ ] **Step 1: Write failing merge and validation tests**

```python
import os
from pathlib import Path

import pytest

from deploy.scripts.config import merge_env_files, validate_environment


def write_env(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_later_layers_override_earlier_layers(tmp_path):
    base = write_env(tmp_path / "base.env", "APP_ENV=dev\nQUERY_MAX_CONCURRENT=8\n")
    profile = write_env(tmp_path / "profile.env", "QUERY_MAX_CONCURRENT=24\n")
    assert merge_env_files((base, profile))["QUERY_MAX_CONCURRENT"] == "24"


def test_duplicate_key_inside_one_file_is_rejected(tmp_path):
    path = write_env(tmp_path / "invalid.env", "APP_ENV=dev\nAPP_ENV=test\n")
    with pytest.raises(ValueError, match="duplicate environment key APP_ENV"):
        merge_env_files((path,))


def test_production_requires_openai_key_for_openai_backend():
    errors = validate_environment(
        {"APP_ENV": "production", "MODEL_BACKEND": "openai", "OPENAI_API_KEY": ""},
        "production",
    )
    assert "OPENAI_API_KEY is required when MODEL_BACKEND=openai" in errors


def test_development_accepts_ollama_without_api_key():
    errors = validate_environment(
        {"APP_ENV": "development", "MODEL_BACKEND": "ollama", "OLLAMA_BASE_URL": "http://localhost:11434"},
        "development",
    )
    assert errors == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda run -n rag-local pytest tests/test_config_generation.py -q`

Expected: FAIL with an import error because `deploy/scripts/config.py` does not exist.

- [ ] **Step 3: Implement the parser and merger**

Use the following behavior in `deploy/scripts/config.py`:

```python
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"invalid environment line {path}:{number}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not KEY_RE.fullmatch(key):
            raise ValueError(f"invalid environment key {key!r} in {path}:{number}")
        if key in values:
            raise ValueError(f"duplicate environment key {key}")
        values[key] = value.strip().strip('"').strip("'")
    return values


def merge_env_files(paths, overrides=None):
    merged: dict[str, str] = {}
    for path in paths:
        merged.update(parse_env_file(Path(path)))
    merged.update({key: value for key, value in (overrides or {}).items() if value is not None})
    return merged
```

- [ ] **Step 4: Implement reusable secret generation**

Use `secrets.token_urlsafe(48)` for application secrets and `secrets.token_urlsafe(32)` for passwords. Generate only missing keys from:

```python
SECRET_KEYS = (
    "POSTGRES_PASSWORD",
    "NEO4J_PASSWORD",
    "REDIS_PASSWORD",
    "JWT_SECRET_KEY",
    "API_SETTINGS_ENCRYPTION_KEY",
    "ADMIN_CREATE_APPROVAL_TOKEN",
)
```

Write `KEY=value` lines with a trailing newline, preserve an existing value byte-for-byte, create parent directories, and set POSIX mode `0o600` when supported. Never print a value.

- [ ] **Step 5: Implement production validation**

`validate_environment` returns error strings, never raises for missing required values. It must enforce:

```text
environment ∈ {development, test, production}
MODEL_BACKEND ∈ {openai, anthropic, ollama, local, custom, deepseek}
production + MODEL_BACKEND=openai      → OPENAI_API_KEY is non-empty
production + MODEL_BACKEND=anthropic   → ANTHROPIC_API_KEY is non-empty
production + MODEL_BACKEND=ollama      → OLLAMA_BASE_URL is non-empty
production                              → DEBUG != true
production                              → CORS_ALLOW_ORIGINS is non-empty and does not contain '*'
production                              → all six SECRET_KEYS are non-empty
```

- [ ] **Step 6: Implement rendering and CLI**

`render_environment` must read `base.env`, the selected environment template, the selected profile, and `.runtime/generated-secrets.env`; apply only explicitly present process variables; validate; write sorted `KEY=value` lines to the output path; and return the merged dictionary. The CLI exits `2` on invalid arguments, `1` on validation errors, and `0` on success.

- [ ] **Step 7: Verify generator behavior**

Run: `conda run -n rag-local pytest tests/test_config_generation.py -q`

Expected: all merge, validation, secret reuse, and output tests pass.

---

## Task 3: Move Compose files to the deployment directory

**Files:**
- Create: `deploy/compose/compose.yaml`, `deploy/compose/compose.dev.yaml`, `deploy/compose/compose.monitoring.yaml`
- Modify: `Dockerfile`
- Test: `tests/test_deploy_assets.py`

**Interfaces:**
- Production invocation uses `docker compose --env-file .runtime/production.env -f deploy/compose/compose.yaml up -d`.
- Development invocation adds `-f deploy/compose/compose.dev.yaml`.
- Monitoring invocation adds `-f deploy/compose/compose.monitoring.yaml`.

- [ ] **Step 1: Add Compose model tests**

```python
import subprocess


def test_production_compose_uses_pinned_images_and_no_database_ports(tmp_path):
    result = subprocess.run(
        ["docker", "compose", "-f", "deploy/compose/compose.yaml", "config"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert ":latest" not in result.stdout
    assert '"5432:5432"' not in result.stdout
    assert '"7687:7687"' not in result.stdout
    assert '"6379:6379"' not in result.stdout
```

The test must skip with a clear reason when Docker is unavailable, so unit tests remain runnable in a non-container environment.

- [ ] **Step 2: Create the production Compose baseline**

Move the existing services into `deploy/compose/compose.yaml`, keeping named volumes and health checks, and make these exact changes:

```yaml
services:
  backend:
    build:
      context: ../..
      dockerfile: Dockerfile
    env_file:
      - ../../.runtime/production.env
  frontend:
    build:
      context: ../..
      dockerfile: Dockerfile.frontend
```

Use fixed versions for PostgreSQL, Neo4j, Redis, n8n, frontend/build images, and monitoring images. Remove host `ports` from postgres, neo4j, and redis in the production baseline. Keep n8n under the `with-n8n` profile.

- [ ] **Step 3: Create development and monitoring overrides**

Development preserves the current source mounts and hot reload, publishes backend `127.0.0.1:8000:8000` and frontend `127.0.0.1:5173:5173`, and uses `.runtime/development.env`.

Monitoring mounts these exact targets:

```text
config/observability/prometheus/prometheus.yml → /etc/prometheus/prometheus.yml
config/observability/prometheus/alert_rules.yml → /etc/prometheus/alert_rules.yml
config/observability/grafana/datasources.yml → /etc/grafana/provisioning/datasources/datasources.yml
config/observability/alertmanager/alertmanager.yml → /etc/alertmanager/alertmanager.yml
```

Monitoring remains explicit and uses fixed image versions. Do not default Grafana credentials to `admin123` in production.

- [ ] **Step 4: Copy deployment tooling into the backend image**

Add this line to the runtime stage of `Dockerfile` after `COPY scripts ./scripts`:

```dockerfile
COPY deploy ./deploy
```

- [ ] **Step 5: Validate Compose combinations**

Run from the repository root after generating development and production runtime env files:

```bash
docker compose --env-file .runtime/production.env -f deploy/compose/compose.yaml config
docker compose --env-file .runtime/development.env -f deploy/compose/compose.yaml -f deploy/compose/compose.dev.yaml config
docker compose --env-file .runtime/production.env -f deploy/compose/compose.yaml -f deploy/compose/compose.monitoring.yaml config
```

Expected: all commands exit `0`; output has no unresolved `${...}` placeholders and no `latest` image tags.

---

## Task 4: Add initialization and health-check tooling

**Files:**
- Create: `deploy/scripts/init_app.py`, `deploy/scripts/healthcheck.py`
- Create: `tests/test_deploy_assets.py` additions

**Interfaces:**
- `python deploy/scripts/init_app.py` imports `app.api.utils.auth_dependencies.auth_service`, which constructs `AuthDBService` and runs its existing idempotent schema initialization.
- `python deploy/scripts/healthcheck.py --url http://127.0.0.1:8000/health --timeout 120` exits `0` only after a successful HTTP response.

- [ ] **Step 1: Write initialization and health tests**

```python
from pathlib import Path


def test_init_app_script_has_no_destructive_database_commands():
    source = Path("deploy/scripts/init_app.py").read_text(encoding="utf-8")
    assert "DROP TABLE" not in source.upper()
    assert "DELETE FROM" not in source.upper()
    assert "down -v" not in source


def test_healthcheck_script_exposes_cli_entrypoint():
    source = Path("deploy/scripts/healthcheck.py").read_text(encoding="utf-8")
    assert "--url" in source
    assert "if __name__ == \"__main__\"" in source
```

- [ ] **Step 2: Implement `init_app.py`**

The script must be equivalent to:

```python
from app.api.utils.auth_dependencies import auth_service


def main() -> int:
    print(f"Application database initialized: {auth_service.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Do not add a second schema implementation.

- [ ] **Step 3: Implement `healthcheck.py`**

Use `urllib.request.urlopen` from the standard library. Accept `--url`, `--timeout`, and `--interval`; retry until the timeout deadline, print only status and error class, and return `1` after the deadline.

- [ ] **Step 4: Run focused tests**

Run: `conda run -n rag-local pytest tests/test_deploy_assets.py -q`

Expected: initialization safety and health CLI tests pass.

---

## Task 5: Implement one-command deployment wrappers

**Files:**
- Create: `deploy/scripts/deploy.sh`, `deploy/scripts/deploy.ps1`
- Modify: `Makefile`
- Test: `tests/test_deploy_assets.py`

**Interfaces:**
- Bash: `./deploy/scripts/deploy.sh production balanced [--monitoring] [--with-n8n]`
- PowerShell: `./deploy/scripts/deploy.ps1 -Environment production -Profile balanced [-Monitoring] [-WithN8n]`
- Make: `make deploy ENV=production PROFILE=balanced`, `make deploy-dev`, `make deploy-monitoring`.

- [ ] **Step 1: Add wrapper static checks**

```python
def test_deploy_wrappers_use_config_renderer_and_safe_compose_commands():
    bash = Path("deploy/scripts/deploy.sh").read_text(encoding="utf-8")
    powershell = Path("deploy/scripts/deploy.ps1").read_text(encoding="utf-8")
    for source in (bash, powershell):
        assert "config.py" in source
        assert "docker compose" in source
        assert "down -v" not in source
        assert "generated-secrets.env" in source
```

- [ ] **Step 2: Implement the Bash wrapper**

The wrapper must use `set -Eeuo pipefail`, resolve the repository root from the script location, validate the two positional arguments against `production|development|test` and `fast|balanced|deep`, call the renderer, run `docker compose config`, call `docker compose up -d`, call `docker compose exec -T backend python deploy/scripts/init_app.py`, and finally call `healthcheck.py`. Optional flags append the monitoring or n8n Compose profile. It must print URLs and safe operational commands without secret values.

- [ ] **Step 3: Implement the PowerShell wrapper**

The PowerShell script must expose typed parameters:

```powershell
param(
  [ValidateSet("development", "test", "production")]
  [string]$Environment = "production",
  [ValidateSet("fast", "balanced", "deep")]
  [string]$Profile = "balanced",
  [switch]$Monitoring,
  [switch]$WithN8n
)
```

It must call the same `config.py` renderer and the same Compose service names as Bash. Use `& docker compose ...` and stop immediately on non-zero exit codes. Do not use `cmd /k`, `start`, or commands that leave unmanaged terminal processes.

- [ ] **Step 4: Update the Makefile**

Replace the existing `up` target with these targets:

```make
config-check:
	conda run -n rag-local python deploy/scripts/config.py validate --environment development --profile balanced

config-init:
	conda run -n rag-local python deploy/scripts/config.py render --environment development --profile balanced --output .runtime/development.env

deploy:
	./deploy/scripts/deploy.sh $(ENV) $(PROFILE)

deploy-dev:
	./deploy/scripts/deploy.sh development balanced

deploy-monitoring:
	./deploy/scripts/deploy.sh production balanced --monitoring
```

Keep `test`, `quality-gate`, `benchmark`, and frontend targets unchanged except for path references that now point to canonical configuration.

- [ ] **Step 5: Verify wrapper preflight behavior**

Run:

```bash
conda run -n rag-local python deploy/scripts/config.py --help
conda run -n rag-local pytest tests/test_deploy_assets.py -q
```

Expected: CLI help exits `0`, static deployment checks pass, and no wrapper contains a destructive volume command.

---

## Task 6: Update documentation and compatibility entrypoints

**Files:**
- Create: `deploy/README.md`, `config/README.md`
- Modify: `README.md`, `docs/getting-started/configuration.md`, `docs/getting-started/quick-start.md`, `docs/operations/docker.md`, `docs/operations/deployment.md`, `docs/operations/quick-deploy.md`, `docs/reference/configuration.md`, `docs/reference/faq.md`, `docs/operations/monitoring/deployment.md`, `scripts/check_docs.py`
- Modify or retain as wrappers: `start.sh`, `start.bat`, `restart.bat`, legacy root Compose files
- Test: `tests/test_deploy_assets.py` and `scripts/check_docs.py`

**Interfaces:**
- Current documentation links to `config/README.md` for configuration ownership.
- Current documentation links to `deploy/README.md` for deployment.
- No current documentation presents `.env.example`, `configs/runtime-profiles`, or root Compose files as the primary workflow.

- [ ] **Step 1: Add documentation path checks**

```python
def test_current_docs_point_to_canonical_deployment_commands():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "deploy/scripts/deploy" in text
    assert "config/env" in text
    assert "docker-compose.yml" not in text
```

- [ ] **Step 2: Write the two canonical READMEs**

`config/README.md` must document source ownership, environment/profile precedence, secret policy, and examples for local development. `deploy/README.md` must document prerequisites, one-command commands for Bash/PowerShell, URLs, service ports, volume names, logs, restart, rollback, and the explicit monitoring/n8n flags.

- [ ] **Step 3: Update public entry points**

Replace the root README Docker quick start with:

```bash
export OPENAI_API_KEY=replace-me
./deploy/scripts/deploy.sh production balanced
```

and the PowerShell equivalent:

```powershell
$env:OPENAI_API_KEY = "replace-me"
powershell -ExecutionPolicy Bypass -File .\deploy\scripts\deploy.ps1 -Environment production -Profile balanced
```

Update local development to use `config/env/development.env.example`, `.runtime/development.env`, and `conda activate rag-local`.

- [ ] **Step 4: Convert old entrypoints to compatibility wrappers**

If retained, each old startup or root Compose file must contain only a migration message and a call/reference to the new canonical command; it must not contain a second service definition or independent environment values. Do not delete ignored local environment files.

- [ ] **Step 5: Run documentation validation**

Run: `conda run -n rag-local python scripts/check_docs.py`

Expected: no forbidden current paths, missing links, or stale primary deployment instructions.

---

## Task 7: Full verification and handoff

**Files:**
- Modify only files required by failures discovered in Tasks 1–6.
- Test: all repository verification commands below.

- [ ] **Step 1: Validate all configuration templates**

Run:

```bash
conda run -n rag-local python deploy/scripts/config.py validate --environment development --profile balanced
conda run -n rag-local python deploy/scripts/config.py validate --environment test --profile fast
```

Expected: both commands exit `0` without printing secret values.

- [ ] **Step 2: Validate Compose models**

Run the three Compose config commands from Task 3 with generated runtime env files.

Expected: all exit `0`, no unresolved variables, no `latest`, and no production database management ports.

- [ ] **Step 3: Run Python tests and lint**

Run:

```bash
conda run -n rag-local pytest tests/test_config_generation.py tests/test_deploy_assets.py tests/test_web_activity_system.py -v
conda run -n rag-local ruff check deploy/scripts app/agents/router_calibration.py tests/test_config_generation.py tests/test_deploy_assets.py
```

Expected: focused tests pass and Ruff reports no errors in changed Python files.

- [ ] **Step 4: Build the frontend**

Run: `npm --prefix frontend run build`

Expected: TypeScript compilation and Vite production build exit `0`.

- [ ] **Step 5: Run the complete test suite**

Run: `conda run -n rag-local pytest tests/ -v`

Expected: no new failures attributable to the configuration/deployment changes; pre-existing unrelated failures are recorded with their exact test names and output.

- [ ] **Step 6: Verify the repository diff**

Run:

```bash
git diff --check
git status --short
```

Confirm that `.runtime/`, real secrets, local logs, data, and unrelated user changes are not staged or modified by the implementation.

