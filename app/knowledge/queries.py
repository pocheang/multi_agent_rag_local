"""One definition of "the same query", shared by the two places that build lists.

`KnowledgeOrchestrator._with_queries` merges rewrite variants into a source plan
and `KnowledgeAgentService._source_plan` now seeds planner sub-queries into one,
so both need to drop duplicates -- and they must agree on what a duplicate is.

It matters more than it looks. `KnowledgeSourcePlan.queries` has no uniqueness
validator, and `reciprocal_rank_fuse` accumulates a contribution per appearance
*within* a list, so the same query twice silently double-weights everything it
returns. A direct plan's single task carries the original question as its prompt,
which is exactly the duplicate that would arise.

This lives here rather than in the orchestrator because the Knowledge Agent must
not import it -- the agent decides what to search, the orchestrator executes it,
and a second copy of this function is how the two would drift apart. Same
reasoning that moved `width.py` out of `app/retrievers/hybrid/`.
"""

from __future__ import annotations

from collections.abc import Sequence


def unique_queries(values: Sequence[str]) -> tuple[str, ...]:
    """Order-preserving de-duplication on case and collapsed whitespace."""

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        query = str(value or "").strip()
        normalized = " ".join(query.lower().split())
        if not query or normalized in seen:
            continue
        seen.add(normalized)
        result.append(query)
    return tuple(result)


__all__ = ["unique_queries"]
