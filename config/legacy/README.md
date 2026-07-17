# Legacy configuration archive

This folder contains tracked examples that used to live at the repository root:

- `.env.example` → use `config/env/development.env.example` and the config renderer.
- `.env.docker.example` → use `config/env/production.env.example` and `deploy/scripts/deploy.*`.

Local ignored files such as `.env`, `.env.security`, `.env.optimized`, and `.env.optimized.recommended` are intentionally not copied here because they may contain credentials or machine-specific values. Rotate any credentials in legacy local files, then let the deployment script regenerate `.runtime/generated-secrets.env`.
