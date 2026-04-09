from functools import lru_cache
import re

from app.core.config import get_settings
from app.services.resilience import call_with_circuit_breaker


@lru_cache(maxsize=1)
def _load_cross_encoder():
    settings = get_settings()
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(settings.reranker_model_name, trust_remote_code=True)
    except Exception:
        return None


_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _lexical_fallback_rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    query_tokens = set(_tokenize(query))
    rescored: list[dict] = []
    for item in candidates:
        text_tokens = set(_tokenize(item.get("text", "")))
        overlap = 0.0
        if query_tokens:
            overlap = len(query_tokens.intersection(text_tokens)) / max(1, len(query_tokens))
        base = float(item.get("hybrid_score", 0.0) or 0.0)
        merged = dict(item)
        merged["rerank_score"] = 0.7 * overlap + 0.3 * base
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
