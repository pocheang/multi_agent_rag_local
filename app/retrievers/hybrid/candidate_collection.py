from collections import defaultdict

from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.hybrid.adaptive_params import adaptive_retrieval_params
from app.retrievers.hybrid.fusion import rrf_score, hybrid_weights
from app.retrievers.hybrid.rank_features import rank_feature_score
from app.retrievers.hybrid.strategy import strategy_flags
from app.retrievers.vector_store import similarity_search
from app.services.query_rewrite import build_rewrite_queries


def safe_similarity_search(
    query: str,
    k: int,
    allowed_sources: list[str] | None = None,
):
    """Wrapper for similarity search with optional source filtering."""
    if allowed_sources is None:
        return similarity_search(query, k=k)
    return similarity_search(query, k=k, allowed_sources=allowed_sources)


def filter_vector_results(vector_results, score_threshold: float) -> list[tuple]:
    """Filter vector results by score threshold."""
    filtered = []
    for row in vector_results:
        if not isinstance(row, tuple) or len(row) != 2:
            continue
        doc, score = row
        try:
            score_value = float(score)
        except Exception:
            continue
        if score_value >= score_threshold:
            filtered.append((doc, score_value))
    return filtered


def collect_candidates(
    query: str,
    allowed_sources: list[str] | None,
    vector_threshold: float,
    settings,
    retrieval_strategy: str | None = None,
    precomputed_vector_results: dict[str, list] | None = None,
    precomputed_raw_vector_results: dict[str, list] | None = None,
) -> tuple[list[dict], dict]:
    """Collect and fuse candidates from vector and BM25 retrieval."""
    rrf_k = int(getattr(settings, "hybrid_rrf_k", 60) or 60)
    flags = strategy_flags(retrieval_strategy)
    vector_top_k, bm25_top_k, reranker_top_n = adaptive_retrieval_params(query, settings, flags["dynamic"])
    vector_weight, bm25_weight = hybrid_weights(settings)

    variants = build_rewrite_queries(
        query,
        enable_llm=bool(flags["rewrite"] and getattr(settings, "query_rewrite_enabled", True) and getattr(settings, "query_rewrite_with_llm", False)),
        use_reasoning=False,
        enable_decompose=bool(flags["decompose"] and getattr(settings, "query_decompose_enabled", True)),
        max_variants=int(getattr(settings, "query_rewrite_max_variants", 6) or 6),
    )
    if not variants:
        variants = [query]

    seen_variants = set()
    unique_variants = []
    for v in variants:
        v_normalized = v.strip().lower()
        if v_normalized not in seen_variants:
            seen_variants.add(v_normalized)
            unique_variants.append(v)
    variants = unique_variants

    merged: dict[str, dict] = {}
    scores = defaultdict(float)
    allowed_set = set(allowed_sources) if allowed_sources is not None else None
    diag = {
        "rewrites": list(variants),
        "vector_hits_by_rewrite": {},
        "bm25_hits_by_rewrite": {},
        "vector_threshold": float(vector_threshold),
        "vector_top_k": vector_top_k,
        "bm25_top_k": bm25_top_k,
        "reranker_top_n": reranker_top_n,
        "strategy": retrieval_strategy or "advanced",
    }

    for variant in variants:
        if precomputed_vector_results and variant in precomputed_vector_results:
            vector_results = precomputed_vector_results[variant]
        elif precomputed_raw_vector_results and variant in precomputed_raw_vector_results:
            vector_results = filter_vector_results(precomputed_raw_vector_results[variant], score_threshold=vector_threshold)
        else:
            vector_results = safe_similarity_search(variant, k=vector_top_k, allowed_sources=allowed_sources)
            vector_results = filter_vector_results(vector_results, score_threshold=vector_threshold)
        diag["vector_hits_by_rewrite"][variant] = len(vector_results)
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
            if not isinstance(existing_dense, (int, float)) or float(score) > float(existing_dense):
                merged[item_id]["dense_score"] = float(score)
            scores[item_id] += vector_weight * rrf_score(idx, rrf_k)

        sparse = bm25_search(variant, k=bm25_top_k, allowed_sources=allowed_sources)
        diag["bm25_hits_by_rewrite"][variant] = len(sparse)
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

    fused = []
    for item_id, item in merged.items():
        candidate = dict(item)
        candidate["hybrid_score"] = float(scores[item_id])
        feature_score = rank_feature_score(candidate, settings) if flags["rank_feature"] else 0.0
        candidate["rank_feature_score"] = feature_score
        candidate["hybrid_score"] = float(candidate["hybrid_score"] + feature_score)
        fused.append(candidate)
    fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
    diag["candidate_count"] = len(fused)
    return fused, diag
