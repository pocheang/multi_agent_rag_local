import logging
import re
from functools import lru_cache

from app.core.config import get_settings
from app.services.runtime.resilience import call_with_circuit_breaker

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_cross_encoder():
    settings = get_settings()
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(
            settings.reranker_model_name,
            trust_remote_code=True,
            local_files_only=True,
        )
        logger.info(f"Successfully loaded reranker model: {settings.reranker_model_name}")
        return model
    except ImportError as e:
        logger.warning(f"sentence-transformers not installed: {e}")
        return None
    except (OSError, ValueError):
        logger.exception(
            f"Reranker model '{settings.reranker_model_name}' not found locally. "
            f"Please download it first:\n"
            f"  from sentence_transformers import CrossEncoder\n"
            f"  CrossEncoder('{settings.reranker_model_name}')"
        )
        return None
    except RuntimeError as e:
        logger.warning(f"Failed to load reranker model: {e}")
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


def lexical_rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    """Public lexical fallback shared by timeout-aware orchestration."""

    return _lexical_fallback_rerank(query, candidates, top_n)


def rerank_with_diagnostics(
    query: str,
    candidates: list[dict],
    top_n: int | None = None,
) -> tuple[list[dict], dict[str, str | None]]:
    """Rerank candidates and report the actual backend and fallback reason."""

    settings = get_settings()
    if not candidates:
        return [], {"reranker_backend": "none", "reranker_fallback_reason": "no_candidates"}
    limit = top_n or settings.reranker_top_n
    if not settings.enable_reranker:
        return _lexical_fallback_rerank(query, candidates, top_n=limit), {
            "reranker_backend": "lexical",
            "reranker_fallback_reason": "disabled",
        }

    model = _load_cross_encoder()
    if model is None:
        return _lexical_fallback_rerank(query, candidates, top_n=limit), {
            "reranker_backend": "lexical",
            "reranker_fallback_reason": "model_unavailable",
        }

    pairs = [[query, item.get("text", "")] for item in candidates]
    try:
        scores = call_with_circuit_breaker("reranker.predict", lambda: model.predict(pairs))
    except (RuntimeError, ValueError) as e:
        logger.warning(f"Reranker prediction failed: {e}, falling back to lexical reranking")
        return _lexical_fallback_rerank(query, candidates, top_n=limit), {
            "reranker_backend": "lexical",
            "reranker_fallback_reason": f"prediction_error:{type(e).__name__}",
        }
    except Exception as e:
        logger.exception(f"Unexpected reranker error: {e}, falling back to lexical reranking")
        return _lexical_fallback_rerank(query, candidates, top_n=limit), {
            "reranker_backend": "lexical",
            "reranker_fallback_reason": f"prediction_error:{type(e).__name__}",
        }

    rescored = []
    for item, score in zip(candidates, scores, strict=False):
        merged = dict(item)
        merged["rerank_score"] = float(score)
        rescored.append(merged)
    rescored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return rescored[:limit], {"reranker_backend": "bge_cross_encoder", "reranker_fallback_reason": None}


def rerank(query: str, candidates: list[dict], top_n: int | None = None) -> list[dict]:
    """Backward-compatible result-only reranker."""

    results, _ = rerank_with_diagnostics(query, candidates, top_n)
    return results


__all__ = ["lexical_rerank", "rerank", "rerank_with_diagnostics"]
