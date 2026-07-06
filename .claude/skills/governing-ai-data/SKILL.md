---
name: governing-ai-data
description: Use when changing data collection, storage, migration, retention, deletion, models, prompts, agents, retrieval, embeddings, tools, or AI evaluation.
---

# Governing AI and Data

Treat data and AI behavior as versioned, tenant-aware product surfaces.

1. Record owners, classification, purpose, affected users/tenants, versions, baseline, and prohibited outcomes.
2. Map data/model flow through storage, indexes, caches, logs, providers, tools, and outputs.
3. Minimize access and permissions; define isolation, retention, deletion, fallback, telemetry, and rollback.
4. Test representative and adversarial slices, including tenant leakage, prompt injection, provider failure, migration, restore, and deletion propagation.
5. Require explicit approval for destructive data operations, sensitive external processing, broader tool permissions, or autonomous actions.

Read [data-lifecycle.md](references/data-lifecycle.md) for storage/migration/retention work. Read [ai-rag.md](references/ai-rag.md) for model/prompt/agent/retrieval work. Use both only when the change crosses both boundaries.
