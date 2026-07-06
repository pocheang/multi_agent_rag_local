# Review and Validation

Review requirements/risk, full diff, affected callers/contracts, correctness, failures, concurrency, compatibility, auth, tenant isolation, validation, secrets/logging, injection, dependencies, AI/tool boundaries, tests, migration, telemetry, and rollback.

Findings include severity, file/line, failure, impact, evidence, and smallest remediation.

Select gates by surface:

```powershell
python -m ruff check <scope>
python -m pytest <target-tests> -v
python -m pytest tests/ -v
npm --prefix frontend run build
python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md artifacts/quality-report.md
```

Add security/tenant, browser, migration, dependency, and RAG slice checks when relevant. Record checks not run. Separate changed-code findings from inherited debt.
