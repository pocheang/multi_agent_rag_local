---
name: planning-work
description: Use when work needs clarification, scope, acceptance criteria, architecture, ownership, risk analysis, decisions, or a test strategy before implementation.
---

# Planning Work

1. Inspect existing code, tests, contracts, data flows, and constraints before asking questions.
2. Separate facts, assumptions, blocking decisions, and safe defaults. Ask only questions that change behavior, architecture, security, data, compatibility, or irreversible actions.
3. Define outcome, scope/non-goals, owner, risk tier, acceptance criteria, dependencies, telemetry, rollout, and rollback.
4. Record consequential choices and map requirements/risks to validation evidence.
5. Stop before implementation if a blocking decision remains.

Read only the matching reference:

- [requirements.md](references/requirements.md): code-ready brief and acceptance criteria.
- [project-governance.md](references/project-governance.md): milestones, RACI, RAID, cadence, change control.
- [decisions.md](references/decisions.md): ADR, RFC, decision and exception records.
- [security-and-tests.md](references/security-and-tests.md): threat model and risk-based test strategy.

Use `developing-change` only after the work is code-ready.
