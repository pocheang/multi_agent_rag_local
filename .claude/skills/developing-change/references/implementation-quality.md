# Implementation and Quality

Loop: reproduce/test, implement one vertical increment, run focused checks, refactor while green, hand off evidence.

Assess correctness, readability, cohesion/coupling, architecture direction, testability, failure handling, security/privacy, performance, compatibility, observability, docs, dependencies, and RAG behavior.

Findings state severity, dimension, location, evidence, impact, smallest remediation, validation, and debt owner/date.

Project checks:

```powershell
python -m ruff check <changed-python-paths>
python -m pytest <target-tests> -v
npm --prefix frontend run build
```

Do not weaken tests to hide failures, reformat unrelated files, or mark quality green from lint/tests alone.
