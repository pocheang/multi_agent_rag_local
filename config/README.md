# Configuration

`config/` is the only source-controlled configuration directory.

- `env/` contains shared, development, test, production, and frontend environment templates.
- `profiles/` contains mutually exclusive runtime strategy overlays: `fast`, `balanced`, and `deep`.
- `application/` contains application JSON configuration (currently: `web_activity_config.json`).
- `observability/` contains Prometheus, Grafana, and Alertmanager configuration.
- `router_calibration.json` (top-level, not under `application/`) is the router confidence
  calibration file — the path is hardcoded in `app/agents/router/calibration.py`.

Runtime configuration is generated into `.runtime/` and is never committed. The merge order is:

```text
base.env < {environment}.env.example < profiles/{profile}.env < .runtime/generated-secrets.env < process overrides
```

Use the generator instead of appending environment files manually:

```bash
conda run -n rag-local python deploy/scripts/config.py render --environment development --profile balanced --output .runtime/development.env
```

Production secrets are generated locally by the deployment script. LLM API keys must be provided through the host environment or an approved secret injection mechanism.

Canonical paths use config/env/ for environment overlays and config/profiles/ for runtime profiles.

Every key in these files must be a `Settings` alias, or listed as deployment-only in
`tests/core/test_config_layers_are_live.py`. `Settings` validates by alias and ignores
everything else, so a key it does not recognise is dropped in silence and still appears in
the rendered `.runtime/*.env` as though it were live — which is how `DEBUG` and
`QUERY_RESULT_CACHE_BACKEND` survived here with no reader anywhere. The test fails on a new
one.
