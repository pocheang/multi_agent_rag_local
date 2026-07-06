---
name: verifying-change
description: Use when reviewing code, designing or running validation, auditing quality, measuring performance, or deciding whether a change is ready.
---

# Verifying a Change

Build evidence proportional to risk.

1. Map acceptance criteria and risks to checks.
2. Review the complete diff and affected contracts before style.
3. Run focused checks, then broader required gates.
4. Record exact command, environment, revision, result, artifacts, failures, and checks not run.
5. Return `PASS`, `FAIL`, or `PASS WITH ACCEPTED RISK/DEBT`; acceptance requires owner, reason, control, and expiry.

Read [review-and-validation.md](references/review-and-validation.md) for review, testing, security, quality, frontend, and RAG gates. Read [performance.md](references/performance.md) only for latency, throughput, capacity, resources, or cost.

Do not treat lint, build, coverage, or an aggregate RAG score as sufficient evidence by itself.
