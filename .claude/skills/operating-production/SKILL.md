---
name: operating-production
description: Use when defining observability or responding to a production alert, outage, degradation, failed deployment, vulnerability, or RAG incident.
---

# Operating Production

Protect users/data, stabilize safely, restore service, then learn.

1. Identify impact/severity, owner, timeline, recent changes, and evidence.
2. Stabilize with the least risky reversible action after authorization.
3. Diagnose with one hypothesis and discriminating evidence; preserve logs, metrics, traces, config, and revision.
4. Verify recovery across user, service, dependency, and quality signals over an observation window.
5. Complete corrective actions with owner/date and recurrence tests.

Read [observability-incidents.md](references/observability-incidents.md) for SLI/SLO, telemetry, alerts, response, and postmortems. Read [rag-diagnostics.md](references/rag-diagnostics.md) only for ingestion, retrieval, routing, grounding, streaming, or RAG quality failures.

Never restart blindly, delete evidence/data, rotate credentials, or perform destructive recovery without explicit authority.
