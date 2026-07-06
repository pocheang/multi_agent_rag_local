---
name: delivery-router
description: Use when selecting an enterprise workflow, auditing lifecycle coverage, or deciding which delivery gate applies.
disable-model-invocation: true
---

# Delivery Router

Use one primary skill per request:

| Work | Skill |
|---|---|
| Clarify, plan, design, threat-model, or define tests | `planning-work` |
| Implement, refactor, branch, commit, change dependencies/contracts | `developing-change` |
| Change data, models, prompts, agents, retrieval, or tools | `governing-ai-data` |
| Review, test, audit quality, benchmark, or prove readiness | `verifying-change` |
| Build pipelines, release, deploy, or roll back | `releasing-deploying` |
| Define SLOs or handle production/RAG incidents | `operating-production` |
| Write reports, runbooks, documentation, or handoffs | `reporting-handoff` |

Risk tiers: **standard** is local/reversible; **elevated** affects contracts, tenants, data, dependencies, performance, or users; **critical** affects production, secrets, security controls, regulated data, destructive operations, or broad AI behavior.

Read [governance.md](references/governance.md) only for gate/role/exception policy. Run `python .claude/skills/delivery-router/scripts/validate_catalog.py` after catalog changes.
