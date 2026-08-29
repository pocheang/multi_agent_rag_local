import json

import app.retrievers.hybrid.candidate_collection as candidate_collection
from app.core.config import get_settings
from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.hybrid.caching import cache_lookup, cache_store, clear_retrieval_cache
from app.retrievers.hybrid.parent_expansion import expand_to_parent_context
from app.retrievers.hybrid.strategy import strategy_flags
from app.retrievers.reranker import rerank_with_diagnostics
from app.retrievers.stores.parent import get_parent_text_map
from app.retrievers.stores.vector import similarity_search
from app.services.observability.tracing import traced_span
from app.services.query.rule_rewrite import build_rewrite_queries


def hybrid_search_with_diagnostics(
    query: str,
    allowed_sources: list[str] | None = None,
    dynamic_top_k: int | None = None,
    dynamic_vector_weight: float | None = None,
    dynamic_bm25_weight: float | None = None,
) -> tuple[list[dict], dict]:
    """Perform hybrid search with full diagnostics."""
    with traced_span("retrieval.hybrid_search", {}):
        settings = get_settings()
        flags = strategy_flags()
        strict_threshold = float(getattr(settings, "vector_similarity_threshold", 0.2) or 0.2)
        relaxed_threshold = float(getattr(settings, "vector_similarity_relaxed_threshold", 0.05) or 0.05)
        degraded = False

        cache_key = json.dumps(
            {
                "q": query,
                "allowed": sorted(allowed_sources) if allowed_sources is not None else None,
                "strict": strict_threshold,
                "relaxed": relaxed_threshold,
                "rrf": getattr(settings, "hybrid_rrf_k", 60),
                "rerank_n": getattr(settings, "reranker_top_n", 5),
                "dynamic_top_k": dynamic_top_k,
                "dynamic_vector_weight": dynamic_vector_weight,
                "dynamic_bm25_weight": dynamic_bm25_weight,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        cached = cache_lookup(cache_key, settings, traced_span)
        if cached:
            return cached

        with traced_span("retrieval.collect_candidates", {}):
            fused, diag = _collect_candidates_for_current_module(
                query,
                allowed_sources=allowed_sources,
                vector_threshold=strict_threshold,
                settings=settings,
                dynamic_top_k=dynamic_top_k,
                dynamic_vector_weight=dynamic_vector_weight,
                dynamic_bm25_weight=dynamic_bm25_weight,
            )

        raw_vector_cache: dict[str, list] = {}
        if not fused and relaxed_threshold < strict_threshold:
            with traced_span("retrieval.degraded_retry", {"relaxed_threshold": relaxed_threshold}):
                flags = strategy_flags()
                vector_top_k = int(getattr(settings, "vector_top_k", 6) or 6)
                variants = build_rewrite_queries(
                    query,
                    enable_llm=bool(
                        flags["rewrite"]
                        and getattr(settings, "query_rewrite_enabled", True)
                        and getattr(settings, "query_rewrite_with_llm", False)
                    ),
                    use_reasoning=False,
                    enable_decompose=bool(flags["decompose"] and getattr(settings, "query_decompose_enabled", True)),
                    max_variants=int(getattr(settings, "query_rewrite_max_variants", 6) or 6),
                )
                if not variants:
                    variants = [query]

                for variant in variants:
                    raw_vector_cache[variant] = _safe_similarity_search(
                        variant, k=vector_top_k, allowed_sources=allowed_sources
                    )

                fused, diag = _collect_candidates_for_current_module(
                    query,
                    allowed_sources=allowed_sources,
                    vector_threshold=relaxed_threshold,
                    settings=settings,
                    precomputed_raw_vector_results=raw_vector_cache,
                    dynamic_top_k=dynamic_top_k,
                    dynamic_vector_weight=dynamic_vector_weight,
                    dynamic_bm25_weight=dynamic_bm25_weight,
                )
                degraded = True
                diag["degraded_reason"] = "strict_threshold_no_results"

        fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)

        rerank_top_n = int(diag.get("reranker_top_n", getattr(settings, "reranker_top_n", 5)) or 5)
        reranked, reranker_diagnostics = rerank_with_diagnostics(query, fused, top_n=rerank_top_n)
        expanded = _expand_to_parent_context(reranked)
        diagnostics = {
            **diag,
            "degraded_to_relaxed_threshold": degraded,
            "strict_threshold": strict_threshold,
            "relaxed_threshold": relaxed_threshold,
            "pre_rerank_count": len(fused),
            "post_rerank_count": len(reranked),
            "post_expand_count": len(expanded),
            "cache_hit": False,
            "cache_backend": "none",
            **reranker_diagnostics,
        }
        cache_store(cache_key, expanded, diagnostics, settings)
        return expanded, diagnostics


def hybrid_search(query: str, allowed_sources: list[str] | None = None) -> list[dict]:
    """Perform hybrid search and return results only."""
    results, _ = hybrid_search_with_diagnostics(query, allowed_sources=allowed_sources)
    return results


def _safe_similarity_search(
    query: str,
    k: int,
    allowed_sources: list[str] | None = None,
):
    """Backward-compatible vector search wrapper using this module's patch point."""
    if allowed_sources is None:
        return similarity_search(query, k=k, require_source_filter=False)
    try:
        return similarity_search(query, k=k, allowed_sources=allowed_sources)
    except TypeError:
        return similarity_search(query, k=k, require_source_filter=False)


def _expand_to_parent_context(candidates: list[dict]) -> list[dict]:
    """Expand candidates to parent context using this module's text-map source."""
    return expand_to_parent_context(candidates, parent_text_map_fn=get_parent_text_map)


def _collect_candidates_for_current_module(
    query: str,
    allowed_sources: list[str] | None,
    vector_threshold: float,
    settings,
    precomputed_raw_vector_results: dict[str, list] | None = None,
    dynamic_top_k: int | None = None,
    dynamic_vector_weight: float | None = None,
    dynamic_bm25_weight: float | None = None,
) -> tuple[list[dict], dict]:
    """Collect candidates using this module's retrieval primitives.

    The primitives are injected explicitly.  They used to be installed by
    reassigning candidate_collection's module globals and restoring them in a
    finally block, which raced whenever two retrievals overlapped -- and this is
    a concurrent path (RAGAgentService gathers query variants across a thread
    pool).
    """
    return candidate_collection.collect_candidates(
        query,
        allowed_sources=allowed_sources,
        vector_threshold=vector_threshold,
        settings=settings,
        precomputed_raw_vector_results=precomputed_raw_vector_results,
        dynamic_top_k=dynamic_top_k,
        dynamic_vector_weight=dynamic_vector_weight,
        dynamic_bm25_weight=dynamic_bm25_weight,
        rewrite_fn=build_rewrite_queries,
        vector_fn=_safe_similarity_search,
        bm25_fn=bm25_search,
    )


def _collect_candidates(
    query: str,
    allowed_sources: list[str] | None = None,
    vector_threshold: float | None = None,
) -> tuple[list[dict], dict]:
    """Backward-compatible wrapper for pre-refactor tests and scripts."""
    settings = get_settings()
    threshold = float(
        vector_threshold
        if vector_threshold is not None
        else getattr(settings, "vector_similarity_threshold", 0.2) or 0.2
    )
    return _collect_candidates_for_current_module(
        query,
        allowed_sources=allowed_sources,
        vector_threshold=threshold,
        settings=settings,
    )


# Re-export clear function and legacy helpers for backward compatibility.
__all__ = [
    "hybrid_search",
    "hybrid_search_with_diagnostics",
    "clear_retrieval_cache",
    "_collect_candidates",
    "_expand_to_parent_context",
    "_safe_similarity_search",
    "similarity_search",
    "bm25_search",
    "get_parent_text_map",
]
