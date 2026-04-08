from functools import lru_cache

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _load_cross_encoder():
    settings = get_settings()
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(settings.reranker_model_name, trust_remote_code=True)
    except Exception:
        return None


def rerank(query: str, candidates: list[dict], top_n: int | None = None) -> list[dict]:
    settings = get_settings()
    if not candidates:
        return []
    if not settings.enable_reranker:
        return candidates[: top_n or settings.reranker_top_n]

    model = _load_cross_encoder()
    if model is None:
        return candidates[: top_n or settings.reranker_top_n]

    pairs = [[query, item.get("text", "")] for item in candidates]
    try:
        scores = model.predict(pairs)
    except Exception:
        return candidates[: top_n or settings.reranker_top_n]

    rescored = []
    for item, score in zip(candidates, scores):
        merged = dict(item)
        merged["rerank_score"] = float(score)
        rescored.append(merged)
    rescored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return rescored[: top_n or settings.reranker_top_n]
