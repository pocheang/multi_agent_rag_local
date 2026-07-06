# Governance

| Gate | Minimum evidence | Owner |
|---|---|---|
| Ready | outcome, scope, owner, risk, acceptance, dependencies | product/technical |
| Design | contracts, decisions, threats, tests, rollout/rollback | technical/security |
| Develop | linked branch/PR, focused tests, reviewable increments | author |
| Verify | exact checks, findings, residual risk/debt | author/reviewer |
| Release | revision, artifact, version, notes, provenance | release |
| Deploy | approval, target, staged rollout, observation, rollback | environment |
| Operate | SLOs, alerts, runbook, incident path | service |
| Close | outcomes, open ownership, evidence, handoff | project/service |

Elevated work requires independent review and targeted regression evidence. Critical work also requires named approval, tested rollback, and post-deployment observation.

Exceptions require owner, reason, affected gate, compensating control, expiry, and follow-up. Skills guide behavior; CI, protected branches, `CODEOWNERS`, scanners, and environment rules must enforce it.
