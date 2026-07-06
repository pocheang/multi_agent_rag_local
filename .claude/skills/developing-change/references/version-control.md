# Version Control

Prefer protected `main` and short-lived trunk-based branches. Use `<type>/<issue>-<slug>` with `feature`, `fix`, `security`, `refactor`, `docs`, `chore`, `release`, or `hotfix`.

Make small coherent commits:

```text
<type>(<scope>): <imperative summary>

Why and non-obvious tradeoff.
Refs: <issue/change/ADR>
```

PRs include purpose, non-goals, risk, decisions, tests, UI evidence, contract/data/config impact, rollout, rollback, and reviewer focus. Prefer squash for ordinary branches unless policy differs. Revert shared history with a new commit.

Pushing, merging, tagging, deleting remote branches, or rewriting history requires explicit authorization.
