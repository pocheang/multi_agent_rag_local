from functools import lru_cache
import re

from app.core.config import get_settings
from app.services.resilience import call_with_circuit_breaker


@lru_cache(maxsize=1)
def _load_cross_encoder():
    settings = get_settings()
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(
            settings.reranker_model_name,
            trust_remote_code=True,
            local_files_only=True,
        )
    except Exception:
        return None


_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _lexical_fallback_rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        # If query has no tokens, return candidates sorted by hybrid_score
        sorted_candidates = sorted(candidates, key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
        for item in sorted_candidates[:top_n]:
            item["rerank_score"] = item.get("hybrid_score", 0.0)
        return sorted_candidates[:top_n]

    rescored: list[dict] = []

    # First pass: calculate scores and find max hybrid_score for normalization
    max_hybrid_score = 0.0
    for item in candidates:
        hybrid_score = float(item.get("hybrid_score", 0.0) or 0.0)
        max_hybrid_score = max(max_hybrid_score, hybrid_score)

    # Normalize hybrid scores to [0, 1] range
    # Use actual max_hybrid_score if it's reasonable, otherwise use 2.0 as fallback
    # Problem: if max_hybrid_score is very small (e.g., 0.1), normalization_factor becomes 2.0
    # This causes all base_normalized to be very small, making overlap dominate
    if max_hybrid_score > 0.01:
        normalization_factor = max_hybrid_score
    else:
        # All scores are near zero, use fixed factor
        normalization_factor = 2.0

    for item in candidates:
        text_tokens = set(_tokenize(item.get("text", "")))
        overlap = 0.0
        if query_tokens:
            overlap = len(query_tokens.intersection(text_tokens)) / len(query_tokens)

        base = float(item.get("hybrid_score", 0.0) or 0.0)
        base_normalized = base / normalization_factor  # Normalize to [0, 1]

        merged = dict(item)
        # Both overlap and base_normalized are now in [0, 1] range
        merged["rerank_score"] = 0.7 * overlap + 0.3 * base_normalized
        rescored.append(merged)

    rescored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return rescored[:top_n]


def rerank(query: str, candidates: list[dict], top_n: int | None = None) -> list[dict]:
    settings = get_settings()
    if not candidates:
        return []
    limit = top_n or settings.reranker_top_n
    if not settings.enable_reranker:
        return _lexical_fallback_rerank(query, candidates, top_n=limit)

    model = _load_cross_encoder()
    if model is None:
        return _lexical_fallback_rerank(query, candidates, top_n=limit)

    pairs = [[query, item.get("text", "")] for item in candidates]
    try:
        scores = call_with_circuit_breaker("reranker.predict", lambda: model.predict(pairs))
    except Exception:
        return _lexical_fallback_rerank(query, candidates, top_n=limit)

    rescored = []
    for item, score in zip(candidates, scores):
        merged = dict(item)
        merged["rerank_score"] = float(score)
        rescored.append(merged)
    rescored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return rescored[:limit]
