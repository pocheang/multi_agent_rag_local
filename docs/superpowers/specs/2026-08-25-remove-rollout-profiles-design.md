# Remove Rollout Profiles Design

## Goal

QueryMind has one retrieval behavior. Remove Canary, Shadow, Baseline, and Safe as executable features and remove every compatibility path that accepts or represents them. Ordinary security terminology, CSS shadows, and generic performance reference language remain outside scope.

## Architecture

The query pipeline owns one retrieval behavior directly. Requests no longer carry a retrieval strategy, runtime state no longer selects a profile, and admin operations no longer expose profile switching, rollback-to-profile, or A/B comparison. Benchmark and replay operations execute the standard pipeline without a strategy parameter.

Configuration contains no retrieval-profile selector or feature-flag percentage rollout. Quality evaluation reports failure without generating a rollback profile. Frontend administration shows benchmark data only and contains no profile state or strategy controls.

## Contracts

- Remove `retrieval_strategy` from pipeline and HTTP request contracts.
- Remove runtime profile functions and `app.services.retrieval.profiles`.
- Remove admin routes `/admin/ops/retrieval-profile`, `/admin/ops/rollback`, and `/admin/ops/ab-compare`.
- Remove Canary route, Shadow module, Baseline evaluation modules, and all related compatibility aliases.
- Old `baseline` and `safe` values are not accepted or normalized.
- Preserve `PipelineProfile` values `standard`, `strict_quality`, and `advanced`; these are query execution profiles, not the removed retrieval rollout profiles.

## Verification

Behavior tests assert removed routes return 404 and removed request fields/symbols are absent. Repository scans must leave only unrelated ordinary meanings. Backend targeted tests, frontend tests/build, Ruff on changed files, `git diff --check`, and the broad test suite provide release evidence.
