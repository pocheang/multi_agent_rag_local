# AI and RAG Governance

Version model/provider, prompt, tool schema, retrieval/index profile, routing, dataset, and baseline. Define intended/prohibited behavior and fallback.

Evaluate normal, difficult, multilingual, empty-context, adversarial, tenant-isolation, prompt-injection, tool-abuse, and provider-failure slices. Measure retrieval, groundedness, citations, task success, safety/refusal, latency, token/cost, and errors. Review slice regressions, not only averages.

Record diff, dataset provenance/limits, reproducible command/artifacts, thresholds, threat/privacy review, monitoring/drift triggers, rollout, rollback, owner, and review date.

Never silently swap production models/prompts, use unapproved sensitive data, or broaden tool permissions without approval.
