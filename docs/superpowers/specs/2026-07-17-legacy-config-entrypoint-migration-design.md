# Legacy Configuration and Entrypoint Migration Design

## Goal

Make `config/` and `deploy/` the only formal configuration and deployment sources while preserving root-level commands as thin compatibility wrappers.

## Decisions

- `config/env/` is the source of truth for environment overlays; `config/profiles/` is the source of truth for retrieval profiles.
- The duplicate tracked `configs/runtime-profiles/` files are removed after verifying they are identical to `config/profiles/`.
- Root `.env.example` and `.env.docker.example` become short migration notices; their complete historical contents move to `config/legacy/env/`.
- Root `docker-compose*.yml` files become Compose `include` wrappers pointing at `deploy/compose/`.
- Root `start*` and `restart.bat` remain callable, but delegate to the canonical development deployment entrypoint instead of hard-coded paths or process-wide kills.
- Local ignored files such as `.env`, `.env.security`, `.env.optimized`, and `.env.optimized.recommended` are not committed or copied. They are documented as legacy local files; secrets must be rotated and regenerated through `.runtime/`.

## Compatibility and Safety

Compatibility wrappers must resolve paths relative to the repository root, never contain developer-specific absolute paths, and must not use destructive volume deletion or process-wide `taskkill`. Canonical Compose files remain pinned and are validated with `docker compose config -q`.

## Validation

Static tests will verify wrapper targets, duplicate profile removal, no hard-coded local paths, no production `latest` images in canonical deployment assets, and no tracked secret files. Compose wrapper files will be validated with Docker Compose after migration.
