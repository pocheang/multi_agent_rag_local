import json

from app.core.config import get_settings
from app.retrievers.hybrid.caching import cache_lookup, cache_store, clear_retrieval_cache
from app.retrievers.hybrid.candidate_collection import collect_candidates, safe_similarity_search
from app.retrievers.hybrid.parent_expansion import expand_to_parent_context
from app.retrievers.hybrid.strategy import strategy_flags
from app.retrievers.reranker import rerank
from app.services.query_rewrite import build_rewrite_queries
from app.services.tracing import traced_span


def hybrid_search_with_diagnostics(
    query: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
) -> tuple[list[dict], dict]:
    """Perform hybrid search with full diagnostics."""
    with traced_span("retrieval.hybrid_search", {"strategy": str(retrieval_strategy or "advanced")}):
        settings = get_settings()
        flags = strategy_flags(retrieval_strategy)
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
                "strategy": retrieval_strategy or "advanced",
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        cached = cache_lookup(cache_key, settings, traced_span)
        if cached:
            return cached

        with traced_span("retrieval.collect_candidates", {"strategy": str(retrieval_strategy or "advanced")}):
            fused, diag = collect_candidates(
                query,
                allowed_sources=allowed_sources,
                vector_threshold=strict_threshold,
                settings=settings,
                retrieval_strategy=retrieval_strategy,
            )

        raw_vector_cache: dict[str, list] = {}
        if not fused and relaxed_threshold < strict_threshold:
            with traced_span("retrieval.degraded_retry", {"relaxed_threshold": relaxed_threshold}):
                flags = strategy_flags(retrieval_strategy)
                vector_top_k = int(getattr(settings, "vector_top_k", 6) or 6)
                variants = build_rewrite_queries(
                    query,
                    enable_llm=bool(flags["rewrite"] and getattr(settings, "query_rewrite_enabled", True) and getattr(settings, "query_rewrite_with_llm", False)),
                    use_reasoning=False,
                    enable_decompose=bool(flags["decompose"] and getattr(settings, "query_decompose_enabled", True)),
                    max_variants=int(getattr(settings, "query_rewrite_max_variants", 6) or 6),
                )
                if not variants:
                    variants = [query]

                for variant in variants:
                    raw_vector_cache[variant] = safe_similarity_search(variant, k=vector_top_k, allowed_sources=allowed_sources)

                fused, diag = collect_candidates(
                    query,
                    allowed_sources=allowed_sources,
                    vector_threshold=relaxed_threshold,
                    settings=settings,
                    retrieval_strategy=retrieval_strategy,
                    precomputed_raw_vector_results=raw_vector_cache,
                )
                degraded = True
                diag["degraded_reason"] = "strict_threshold_no_results"

        fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)

        rerank_top_n = int(diag.get("reranker_top_n", getattr(settings, "reranker_top_n", 5)) or 5)
        reranked = rerank(query, fused, top_n=rerank_top_n)
        expanded = expand_to_parent_context(reranked)
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
        }
        cache_store(cache_key, expanded, diagnostics, settings)
        return expanded, diagnostics


def hybrid_search(query: str, allowed_sources: list[str] | None = None, retrieval_strategy: str | None = None) -> list[dict]:
    """Perform hybrid search and return results only."""
    results, _ = hybrid_search_with_diagnostics(query, allowed_sources=allowed_sources, retrieval_strategy=retrieval_strategy)
    return results


# Re-export clear function for backward compatibility
__all__ = ["hybrid_search", "hybrid_search_with_diagnostics", "clear_retrieval_cache"]
