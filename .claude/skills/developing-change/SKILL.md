---
name: developing-change
description: Use when code-ready work is being implemented, refactored, version-controlled, or changing dependencies or consumer-visible contracts.
---

# Developing a Change

1. Confirm the code-ready brief, risk tier, and focused failing test or reproduction.
2. Inspect `git status`; preserve unrelated work and trace affected callers/contracts.
3. Implement the smallest vertical increment. Keep auth, tenant context, timeout, cancellation, errors, compatibility, and observability explicit.
4. Run narrow checks after each increment and leave a reviewable handoff.
5. Never commit secrets, production data, logs, caches, or unrelated formatting.

Read only the matching reference:

- [version-control.md](references/version-control.md): branches, commits, PRs, merge, tags, revert.
- [implementation-quality.md](references/implementation-quality.md): implementation loop and code-quality model.
- [module-design.md](references/module-design.md): small files, repair/generation/refactor modes, modularity, extension points.
- [dependencies-contracts.md](references/dependencies-contracts.md): dependency supply chain and API/schema evolution.

Use `governing-ai-data` for data or AI behavior and `verifying-change` for final evidence.
