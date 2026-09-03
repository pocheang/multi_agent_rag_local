import logging
from collections import defaultdict

from app.knowledge.width import adaptive_retrieval_params
from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.hybrid.fusion import hybrid_weights, rrf_score
from app.retrievers.hybrid.rank_features import rank_feature_score
from app.retrievers.hybrid.strategy import strategy_flags
from app.services.query.rule_rewrite import build_rewrite_queries

logger = logging.getLogger(__name__)


def filter_vector_results(vector_results, score_threshold: float) -> list[tuple]:
    """Filter vector results by score threshold."""
    filtered = []
    for row in vector_results:
        if not isinstance(row, tuple) or len(row) != 2:
            continue
        doc, score = row
        try:
            score_value = float(score)
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid score value, skipping: {e}")
            continue
        if score_value >= score_threshold:
            filtered.append((doc, score_value))
    return filtered


def collect_candidates(
    query: str,
    allowed_sources: list[str] | None,
    vector_threshold: float,
    settings,
    precomputed_vector_results: dict[str, list] | None = None,
    precomputed_raw_vector_results: dict[str, list] | None = None,
    dynamic_top_k: int | None = None,
    dynamic_vector_weight: float | None = None,
    dynamic_bm25_weight: float | None = None,
    *,
    vector_fn,
    rewrite_fn=None,
    bm25_fn=None,
) -> tuple[list[dict], dict]:
    """Collect and fuse candidates from vector and BM25 retrieval.

    ``rewrite_fn`` / ``vector_fn`` / ``bm25_fn`` let a caller substitute the
    retrieval primitives for one call; callers previously achieved the same
    effect by reassigning module globals, which raced across concurrent
    requests.

    ``vector_fn`` is required and has no default, where the other two are
    optional.  The difference is ownership: the vector hop is the one that
    reaches the store, and the store's own metadata check needs an ``OwnerScope``
    this function has no way to supply.  The default that used to sit here called
    ``similarity_search`` without one -- unreachable in practice, since the live
    caller injects an owner-bound partial, but a ready-made way back to an
    ownership-blind search for the next caller who omits the argument.  Omitting
    it is now a TypeError.
    """
    _rewrite = rewrite_fn or build_rewrite_queries
    _vector = vector_fn
    _bm25 = bm25_fn or bm25_search
    rrf_k = int(getattr(settings, "hybrid_rrf_k", 60) or 60)
    flags = strategy_flags()

    vector_top_k, bm25_top_k, reranker_top_n = _retrieval_width(query, settings, flags, dynamic_top_k)
    vector_weight, bm25_weight = _fusion_weights(settings, dynamic_vector_weight, dynamic_bm25_weight)
    variants = _query_variants(query, settings, flags, _rewrite)

    merged: dict[str, dict] = {}
    scores: dict[str, float] = defaultdict(float)
    allowed_set = set(allowed_sources) if allowed_sources is not None else None
    diag = {
        "rewrites": list(variants),
        "vector_hits_by_rewrite": {},
        "bm25_hits_by_rewrite": {},
        "vector_threshold": float(vector_threshold),
        "vector_top_k": vector_top_k,
        "bm25_top_k": bm25_top_k,
        "reranker_top_n": reranker_top_n,
        "vector_weight": vector_weight,
        "bm25_weight": bm25_weight,
        "dynamic_params_applied": dynamic_top_k is not None,
    }

    for variant in variants:
        vector_results = _vector_hits(
            variant,
            vector_fn=_vector,
            allowed_sources=allowed_sources,
            top_k=vector_top_k,
            threshold=vector_threshold,
            precomputed=precomputed_vector_results,
            precomputed_raw=precomputed_raw_vector_results,
        )
        diag["vector_hits_by_rewrite"][variant] = len(vector_results)
        _merge_vector_hits(merged, scores, vector_results, allowed_set, vector_weight, rrf_k)

        sparse = _bm25(variant, k=bm25_top_k, allowed_sources=allowed_sources)
        diag["bm25_hits_by_rewrite"][variant] = len(sparse)
        _merge_bm25_hits(merged, scores, sparse, allowed_set, bm25_weight, rrf_k)

    fused = _fuse(merged, scores, settings, flags)
    diag["candidate_count"] = len(fused)
    return fused, diag


def _retrieval_width(query: str, settings, flags: dict, dynamic_top_k: int | None) -> tuple[int, int, int]:
    """How wide to search. A caller-supplied width wins over the adaptive one."""

    if dynamic_top_k is None:
        return adaptive_retrieval_params(query, settings, flags["dynamic"])
    # The caller sized the search, not the rerank: feeding the reranker more
    # candidates while holding its output fixed only discards the extra ones.
    return dynamic_top_k, dynamic_top_k, int(getattr(settings, "reranker_top_n", 5) or 5)


def _fusion_weights(settings, dynamic_vector_weight: float | None, dynamic_bm25_weight: float | None):
    """Both dynamic weights or neither -- one of a normalized pair means nothing on its own."""

    if dynamic_vector_weight is not None and dynamic_bm25_weight is not None:
        return dynamic_vector_weight, dynamic_bm25_weight
    return hybrid_weights(settings)


def _query_variants(query: str, settings, flags: dict, rewrite_fn) -> list[str]:
    """The queries to actually search for, deduplicated but in the order proposed.

    Case and surrounding space do not make a different search, and a rewriter
    that returns nothing leaves the question as asked.
    """

    variants = rewrite_fn(
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

    seen: set[str] = set()
    unique: list[str] = []
    for variant in variants:
        normalized = variant.strip().lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(variant)
    return unique


def _vector_hits(
    variant: str,
    *,
    vector_fn,
    allowed_sources: list[str] | None,
    top_k: int,
    threshold: float,
    precomputed: dict[str, list] | None,
    precomputed_raw: dict[str, list] | None,
) -> list[tuple]:
    """Vector hits for one variant, from whichever of the three sources has them.

    ``precomputed`` is taken as already filtered; ``precomputed_raw`` and a live
    search are not.
    """

    if precomputed and variant in precomputed:
        return precomputed[variant]
    if precomputed_raw and variant in precomputed_raw:
        return filter_vector_results(precomputed_raw[variant], score_threshold=threshold)
    results = vector_fn(variant, k=top_k, allowed_sources=allowed_sources)
    return filter_vector_results(results, score_threshold=threshold)


def _merge_vector_hits(
    merged: dict[str, dict],
    scores: dict[str, float],
    vector_results: list[tuple],
    allowed_set: set[str] | None,
    vector_weight: float,
    rrf_k: int,
) -> None:
    """Fold one variant's dense hits in, scoring by rank and keeping the best score.

    The source check repeats what the store was asked to scope: this is the
    second of the two independent checks, on what actually came back.
    """

    for idx, (doc, score) in enumerate(vector_results, start=1):
        metadata = dict(doc.metadata)
        source = str(metadata.get("source", "") or "")
        if allowed_set is not None and source not in allowed_set:
            continue
        item_id = metadata.get("chunk_id") or f"vector::{idx}::{metadata.get('source', 'unknown')}"
        merged.setdefault(
            item_id,
            {
                "id": item_id,
                "text": doc.page_content,
                "metadata": metadata,
                "dense_score": float(score),
                "retrieval_sources": ["vector"],
            },
        )
        existing_dense = merged[item_id].get("dense_score")
        if not isinstance(existing_dense, int | float) or float(score) > float(existing_dense):
            merged[item_id]["dense_score"] = float(score)
        scores[item_id] += vector_weight * rrf_score(idx, rrf_k)


def _merge_bm25_hits(
    merged: dict[str, dict],
    scores: dict[str, float],
    sparse: list[dict],
    allowed_set: set[str] | None,
    bm25_weight: float,
    rrf_k: int,
) -> None:
    """Fold one variant's sparse hits in, recording both retrievers where they agree."""

    for idx, item in enumerate(sparse, start=1):
        source = str((item.get("metadata", {}) or {}).get("source", "") or "")
        if allowed_set is not None and source not in allowed_set:
            continue
        item_id = item["id"]
        existing = merged.get(item_id)
        if existing:
            if "bm25" not in existing["retrieval_sources"]:
                existing["retrieval_sources"].append("bm25")
            existing["bm25_score"] = max(float(existing.get("bm25_score", 0.0)), float(item.get("bm25_score", 0.0)))
        else:
            merged[item_id] = {
                "id": item_id,
                "text": item["text"],
                "metadata": item.get("metadata", {}),
                "bm25_score": float(item.get("bm25_score", 0.0)),
                "retrieval_sources": ["bm25"],
            }
        scores[item_id] += bm25_weight * rrf_score(idx, rrf_k)


def _fuse(merged: dict[str, dict], scores: dict[str, float], settings, flags: dict) -> list[dict]:
    """Rank the merged candidates by their fused RRF score plus rank features."""

    fused = []
    for item_id, item in merged.items():
        candidate = dict(item)
        feature_score = rank_feature_score(candidate, settings) if flags["rank_feature"] else 0.0
        candidate["rank_feature_score"] = feature_score
        candidate["hybrid_score"] = float(scores[item_id]) + feature_score
        fused.append(candidate)
    fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
    return fused
