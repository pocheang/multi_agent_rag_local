"""How wide a retrieval should be, given the query and the plan.

This is retrieval *planning*, so it lives next to the Knowledge Agent rather
than inside a retriever: the Agent decides the shape of a search and the
orchestrator executes it. `app/retrievers/hybrid/` still re-exports
`adaptive_retrieval_params` under its old name for the legacy hybrid path.

The complexity signal is deliberately one definition with two call sites. The
hybrid retriever scales `VECTOR_TOP_K`/`BM25_TOP_K` (6); the Knowledge Agent
scales `TOP_K` (4). Same formula, different bases, so neither path silently
inherits the other's default width.
"""

from __future__ import annotations

import re

_COMPLEX_HINT_RE = re.compile(
    r"(对比|比较|trade[- ]?off|architecture|timeline|root cause|复盘|多阶段|attack chain)",
    flags=re.IGNORECASE,
)

MAX_SCALE = 2
"""Complexity is capped before it is applied: the caps below are the real
ceiling, and an unbounded scale would make them the only thing standing between
a long question and a retrieval that empties the corpus."""


def query_complexity(query: str) -> int:
    """Score 0-3 on how much retrieval a question is likely to need."""
    text = str(query or "")
    token_count = len(re.findall(r"[A-Za-z0-9_]+|[一-鿿]", text))
    complexity = 0
    if token_count >= 28:
        complexity += 1
    if _COMPLEX_HINT_RE.search(text):
        complexity += 1
    if text.count("?") + text.count("？") >= 2:
        complexity += 1
    return complexity


def widen(base: int, cap: int, scale: int, *, step: int) -> int:
    """Grow `base` by `step` per complexity point, never past `cap`."""
    if scale <= 0:
        return base
    return min(max(base, cap), base + (step * scale))


def adaptive_retrieval_params(query: str, settings, dynamic_enabled: bool) -> tuple[int, int, int]:
    """Dynamically adjust retrieval parameters based on query complexity."""
    vector_top_k = int(getattr(settings, "vector_top_k", 6) or 6)
    bm25_top_k = int(getattr(settings, "bm25_top_k", 6) or 6)
    reranker_top_n = int(getattr(settings, "reranker_top_n", 5) or 5)
    if not dynamic_enabled:
        return vector_top_k, bm25_top_k, reranker_top_n

    scale = min(MAX_SCALE, query_complexity(query))
    if scale <= 0:
        return vector_top_k, bm25_top_k, reranker_top_n

    return (
        widen(vector_top_k, int(getattr(settings, "dynamic_vector_top_k_cap", 16) or 16), scale, step=2),
        widen(bm25_top_k, int(getattr(settings, "dynamic_bm25_top_k_cap", 16) or 16), scale, step=2),
        widen(reranker_top_n, int(getattr(settings, "dynamic_reranker_top_n_cap", 10) or 10), scale, step=1),
    )


__all__ = ["MAX_SCALE", "adaptive_retrieval_params", "query_complexity", "widen"]
