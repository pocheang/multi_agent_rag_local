"""Reranker impact metrics built on the repository's canonical retrieval metrics."""

from __future__ import annotations

from app.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank


def reranker_lift(
    before: list[str],
    after: list[str],
    relevant: set[str],
    *,
    k: int = 5,
) -> dict[str, float]:
    before_scores = {
        "recall_at_k": recall_at_k(before, relevant, k),
        "mrr": reciprocal_rank(before, relevant),
        "ndcg_at_k": ndcg_at_k(before, relevant, k),
    }
    after_scores = {
        "recall_at_k": recall_at_k(after, relevant, k),
        "mrr": reciprocal_rank(after, relevant),
        "ndcg_at_k": ndcg_at_k(after, relevant, k),
    }
    return {
        **{f"before_{name}": value for name, value in before_scores.items()},
        **{f"after_{name}": value for name, value in after_scores.items()},
        **{f"lift_{name}": after_scores[name] - before_scores[name] for name in before_scores},
    }


__all__ = ["reranker_lift"]
