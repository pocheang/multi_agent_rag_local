from collections import defaultdict
from datetime import datetime, timezone
import re
import json

from app.core.config import get_settings
from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.parent_store import get_parent_text_map
from app.retrievers.reranker import rerank
from app.retrievers.vector_store import similarity_search
from app.services.query_rewrite import build_rewrite_queries
from app.services.resilience import TTLCache
from app.services.tracing import traced_span

_RETRIEVAL_CACHE: TTLCache | None = None
_REDIS_CLIENT = None


def _rrf_score(rank: int, k: int) -> float:
    return 1.0 / (k + rank)


def _safe_similarity_search(
    query: str,
    k: int,
    allowed_sources: list[str] | None = None,
):
    if allowed_sources is None:
        return similarity_search(query, k=k)
    return similarity_search(query, k=k, allowed_sources=allowed_sources)


def _filter_vector_results(vector_results, score_threshold: float) -> list[tuple]:
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


def _hybrid_weights(settings) -> tuple[float, float]:
    vector_weight = float(getattr(settings, "hybrid_vector_weight", 0.95) or 0.95)
    bm25_weight = float(getattr(settings, "hybrid_bm25_weight", 0.05) or 0.05)
    total = vector_weight + bm25_weight
    if total <= 0:
        return 0.95, 0.05
    return vector_weight / total, bm25_weight / total


def _collect_candidates(
    query: str,
    allowed_sources: list[str] | None,
    vector_threshold: float,
    retrieval_strategy: str | None = None,
    precomputed_vector_results: dict[str, list] | None = None,
    precomputed_raw_vector_results: dict[str, list] | None = None,
) -> tuple[list[dict], dict]:
    settings = get_settings()
    rrf_k = int(getattr(settings, "hybrid_rrf_k", 60) or 60)
    flags = _strategy_flags(retrieval_strategy)
    vector_top_k, bm25_top_k, reranker_top_n = _adaptive_retrieval_params(query, settings, flags["dynamic"])
    vector_weight, bm25_weight = _hybrid_weights(settings)

    variants = build_rewrite_queries(
        query,
        enable_llm=bool(flags["rewrite"] and getattr(settings, "query_rewrite_enabled", True) and getattr(settings, "query_rewrite_with_llm", False)),
        use_reasoning=False,
        enable_decompose=bool(flags["decompose"] and getattr(settings, "query_decompose_enabled", True)),
        max_variants=int(getattr(settings, "query_rewrite_max_variants", 6) or 6),
    )
    if not variants:
        variants = [query]

    # Deduplicate variants while preserving order
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
        # Use precomputed filtered results if available
        if precomputed_vector_results and variant in precomputed_vector_results:
            vector_results = precomputed_vector_results[variant]
        # Use precomputed raw results and re-filter with new threshold
        elif precomputed_raw_vector_results and variant in precomputed_raw_vector_results:
            vector_results = _filter_vector_results(precomputed_raw_vector_results[variant], score_threshold=vector_threshold)
        # Fetch fresh results
        else:
            vector_results = _safe_similarity_search(variant, k=vector_top_k, allowed_sources=allowed_sources)
            vector_results = _filter_vector_results(vector_results, score_threshold=vector_threshold)
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
            scores[item_id] += vector_weight * _rrf_score(idx, rrf_k)

        sparse = bm25_search(variant, k=bm25_top_k, allowed_sources=allowed_sources)
        diag["bm25_hits_by_rewrite"][variant] = len(sparse)
        for idx, item in enumerate(sparse, start=1):
            # Note: bm25_search should already filter by allowed_sources,
            # but we keep this check for defensive programming and test compatibility
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
            scores[item_id] += bm25_weight * _rrf_score(idx, rrf_k)

    fused = []
    for item_id, item in merged.items():
        candidate = dict(item)
        candidate["hybrid_score"] = float(scores[item_id])
        # Apply rank feature score immediately during candidate collection
        feature_score = _rank_feature_score(candidate, settings) if flags["rank_feature"] else 0.0
        candidate["rank_feature_score"] = feature_score
        candidate["hybrid_score"] = float(candidate["hybrid_score"] + feature_score)
        fused.append(candidate)
    fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
    diag["candidate_count"] = len(fused)
    return fused, diag


_COMPLEX_HINT_RE = re.compile(
    r"(对比|比较|trade[- ]?off|architecture|timeline|root cause|复盘|多阶段|attack chain)",
    flags=re.IGNORECASE,
)


def _adaptive_retrieval_params(query: str, settings, dynamic_enabled: bool) -> tuple[int, int, int]:
    vector_top_k = int(getattr(settings, "vector_top_k", 6) or 6)
    bm25_top_k = int(getattr(settings, "bm25_top_k", 6) or 6)
    reranker_top_n = int(getattr(settings, "reranker_top_n", 5) or 5)
    if not dynamic_enabled:
        return vector_top_k, bm25_top_k, reranker_top_n

    q = str(query or "")
    token_count = len(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", q))
    complexity = 0
    if token_count >= 28:
        complexity += 1
    if _COMPLEX_HINT_RE.search(q):
        complexity += 1
    if q.count("?") + q.count("？") >= 2:
        complexity += 1

    if complexity <= 0:
        return vector_top_k, bm25_top_k, reranker_top_n

    vector_cap = int(getattr(settings, "dynamic_vector_top_k_cap", 16) or 16)
    bm25_cap = int(getattr(settings, "dynamic_bm25_top_k_cap", 16) or 16)
    rerank_cap = int(getattr(settings, "dynamic_reranker_top_n_cap", 10) or 10)
    scale = min(2, complexity)
    vector_top_k = min(vector_cap, vector_top_k + (2 * scale))
    bm25_top_k = min(bm25_cap, bm25_top_k + (2 * scale))
    reranker_top_n = min(rerank_cap, reranker_top_n + scale)
    return vector_top_k, bm25_top_k, reranker_top_n


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        # tolerate trailing Z
        raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _rank_feature_score(item: dict, settings) -> float:
    if not bool(getattr(settings, "rank_feature_enabled", True)):
        return 0.0
    metadata = item.get("metadata", {}) or {}
    source_weight = float(getattr(settings, "rank_feature_source_weight", 0.08) or 0.08)
    freshness_weight = float(getattr(settings, "rank_feature_freshness_weight", 0.07) or 0.07)
    diversity_weight = float(getattr(settings, "rank_feature_retrieval_diversity_weight", 0.05) or 0.05)

    source_signal = 0.0
    src = str(metadata.get("source", "")).lower()
    if src:
        # Simple trust heuristic: markdown/pdf/doc are often curated corpora in local RAG.
        if src.endswith((".md", ".pdf", ".docx", ".txt")):
            source_signal = 1.0
        else:
            source_signal = 0.6

    freshness_signal = 0.0
    for key in ("updated_at", "created_at", "ingested_at", "timestamp"):
        dt = _parse_iso_datetime(str(metadata.get(key, "")))
        if not dt:
            continue
        age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        freshness_signal = max(0.0, 1.0 - min(age_days / 365.0, 1.0))
        break

    retrieval_sources = item.get("retrieval_sources", [])
    if not isinstance(retrieval_sources, list):
        retrieval_sources = [str(retrieval_sources)]
    diversity_signal = min(1.0, len(set([str(x) for x in retrieval_sources])) / 2.0)

    return (source_weight * source_signal) + (freshness_weight * freshness_signal) + (diversity_weight * diversity_signal)


def _strategy_flags(retrieval_strategy: str | None) -> dict[str, bool]:
    strategy = str(retrieval_strategy or "advanced").strip().lower()
    if strategy == "baseline":
        return {"rewrite": False, "decompose": False, "dynamic": False, "rank_feature": False}
    if strategy == "safe":
        return {"rewrite": True, "decompose": False, "dynamic": False, "rank_feature": False}
    return {"rewrite": True, "decompose": True, "dynamic": True, "rank_feature": True}


def _cache_backend(settings) -> str:
    raw = str(getattr(settings, "retrieval_cache_backend", "auto") or "auto").strip().lower()
    if raw in {"off", "none", "disabled"}:
        return "off"
    if raw in {"memory", "redis"}:
        return raw
    return "auto"


def _redis_client(settings):
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    try:
        import redis  # type: ignore
    except Exception:
        return None
    try:
        _REDIS_CLIENT = redis.from_url(str(getattr(settings, "redis_url", "")))
        _REDIS_CLIENT.ping()
    except Exception:
        _REDIS_CLIENT = None
    return _REDIS_CLIENT


def clear_retrieval_cache() -> None:
    global _RETRIEVAL_CACHE
    _RETRIEVAL_CACHE = None
    try:
        settings = get_settings()
        backend = _cache_backend(settings)
        if backend not in {"redis", "auto"}:
            return
        client = _redis_client(settings)
        if client is None:
            return
        keys = list(client.scan_iter(match="retrieval:*", count=500))
        if keys:
            client.delete(*keys)
    except Exception:
        return


def _expand_to_parent_context(candidates: list[dict]) -> list[dict]:
    parent_ids: list[str] = []
    for item in candidates:
        parent_id = str((item.get("metadata", {}) or {}).get("parent_id", "")).strip()
        if parent_id:
            parent_ids.append(parent_id)
    parent_map = get_parent_text_map(parent_ids)

    expanded: list[dict] = []
    seen: set[str] = set()
    parent_score_map: dict[str, float] = {}

    for item in candidates:
        metadata = dict(item.get("metadata", {}) or {})
        parent_id = str(metadata.get("parent_id", "")).strip()
        dedupe_key = parent_id or str(item.get("id", ""))

        current_score = item.get("hybrid_score", 0.0)
        if dedupe_key in seen:
            if parent_id and current_score > parent_score_map.get(parent_id, 0.0):
                for idx, existing in enumerate(expanded):
                    if existing.get("metadata", {}).get("parent_id") == parent_id:
                        # Update with higher-scored item, preserving all scores
                        updated = dict(item)
                        updated["child_text"] = item.get("text", "")
                        if parent_map.get(parent_id):
                            updated["text"] = parent_map[parent_id]
                            metadata["context_granularity"] = "parent"
                        else:
                            metadata["context_granularity"] = "child"
                        updated["metadata"] = metadata
                        # Preserve all score fields from the higher-scored item
                        updated["hybrid_score"] = current_score
                        updated["dense_score"] = item.get("dense_score")
                        updated["bm25_score"] = item.get("bm25_score")
                        updated["rerank_score"] = item.get("rerank_score")
                        updated["rank_feature_score"] = item.get("rank_feature_score")
                        updated["retrieval_sources"] = item.get("retrieval_sources", [])
                        expanded[idx] = updated
                        parent_score_map[parent_id] = current_score
                        break
            continue

        seen.add(dedupe_key)
        if parent_id:
            parent_score_map[parent_id] = current_score

        merged = dict(item)
        if parent_id and parent_map.get(parent_id):
            merged["child_text"] = item.get("text", "")
            merged["text"] = parent_map[parent_id]
            metadata["context_granularity"] = "parent"
        else:
            metadata["context_granularity"] = "child"
        merged["metadata"] = metadata
        expanded.append(merged)
    return expanded


def hybrid_search_with_diagnostics(
    query: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
) -> tuple[list[dict], dict]:
    with traced_span("retrieval.hybrid_search", {"strategy": str(retrieval_strategy or "advanced")}):
        settings = get_settings()
        flags = _strategy_flags(retrieval_strategy)
        global _RETRIEVAL_CACHE
        if _RETRIEVAL_CACHE is None:
            _RETRIEVAL_CACHE = TTLCache(
                ttl_seconds=int(getattr(settings, "retrieval_cache_ttl_seconds", 45) or 45),
                max_items=int(getattr(settings, "retrieval_cache_max_items", 256) or 256),
            )
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
        backend = _cache_backend(settings)
        use_cache = bool(getattr(settings, "retrieval_cache_enabled", True)) and backend != "off"
        if use_cache:
            with traced_span("retrieval.cache_lookup", {"backend": backend}):
                if backend in {"redis", "auto"}:
                    client = _redis_client(settings)
                else:
                    client = None
                if client is not None:
                    try:
                        raw = client.get(f"retrieval:{cache_key}")
                        if raw:
                            payload = json.loads(raw)
                            out_diag = dict(payload.get("diagnostics", {}))
                            out_diag["cache_hit"] = True
                            out_diag["cache_backend"] = "redis"
                            return list(payload.get("results", [])), out_diag
                    except Exception as e:
                        # Redis cache lookup failed, fall back to memory cache
                        import logging
                        logging.getLogger(__name__).debug(f"Redis cache lookup failed, falling back to memory: {type(e).__name__}")
                cached = _RETRIEVAL_CACHE.get(cache_key)
                if cached:
                    results, diagnostics = cached
                    out_diag = dict(diagnostics)
                    out_diag["cache_hit"] = True
                    out_diag["cache_backend"] = "memory"
                    return list(results), out_diag

        with traced_span("retrieval.collect_candidates", {"strategy": str(retrieval_strategy or "advanced")}):
            fused, diag = _collect_candidates(
                query,
                allowed_sources=allowed_sources,
                vector_threshold=strict_threshold,
                retrieval_strategy=retrieval_strategy,
            )

        # If no results with strict threshold, retry with relaxed threshold
        # Optimization: cache raw vector results to avoid duplicate queries
        raw_vector_cache: dict[str, list] = {}
        if not fused and relaxed_threshold < strict_threshold:
            with traced_span("retrieval.degraded_retry", {"relaxed_threshold": relaxed_threshold}):
                # Build raw vector cache from first attempt
                settings_obj = get_settings()
                flags = _strategy_flags(retrieval_strategy)
                vector_top_k = int(getattr(settings_obj, "vector_top_k", 6) or 6)
                variants = build_rewrite_queries(
                    query,
                    enable_llm=bool(flags["rewrite"] and getattr(settings_obj, "query_rewrite_enabled", True) and getattr(settings_obj, "query_rewrite_with_llm", False)),
                    use_reasoning=False,
                    enable_decompose=bool(flags["decompose"] and getattr(settings_obj, "query_decompose_enabled", True)),
                    max_variants=int(getattr(settings_obj, "query_rewrite_max_variants", 6) or 6),
                )
                if not variants:
                    variants = [query]

                # Fetch raw results once and cache them
                for variant in variants:
                    raw_vector_cache[variant] = _safe_similarity_search(variant, k=vector_top_k, allowed_sources=allowed_sources)

                # Re-run collection with relaxed threshold using cached raw results
                fused, diag = _collect_candidates(
                    query,
                    allowed_sources=allowed_sources,
                    vector_threshold=relaxed_threshold,
                    retrieval_strategy=retrieval_strategy,
                    precomputed_raw_vector_results=raw_vector_cache,
                )
                degraded = True
                diag["degraded_reason"] = "strict_threshold_no_results"

        # rank_feature_score already applied in _collect_candidates, just re-sort
        fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)

        rerank_top_n = int(diag.get("reranker_top_n", getattr(settings, "reranker_top_n", 5)) or 5)
        reranked = rerank(query, fused, top_n=rerank_top_n)
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
        }
        if use_cache:
            _RETRIEVAL_CACHE.set(cache_key, (list(expanded), dict(diagnostics)))
            if backend in {"redis", "auto"}:
                client = _redis_client(settings)
                if client is not None:
                    try:
                        client.setex(
                            f"retrieval:{cache_key}",
                            int(getattr(settings, "retrieval_cache_ttl_seconds", 45) or 45),
                            json.dumps({"results": expanded, "diagnostics": diagnostics}, ensure_ascii=False),
                        )
                        diagnostics["cache_backend"] = "redis"
                    except Exception:
                        diagnostics["cache_backend"] = "memory"
                else:
                    diagnostics["cache_backend"] = "memory"
        return expanded, diagnostics


def hybrid_search(query: str, allowed_sources: list[str] | None = None, retrieval_strategy: str | None = None) -> list[dict]:
    results, _ = hybrid_search_with_diagnostics(query, allowed_sources=allowed_sources, retrieval_strategy=retrieval_strategy)
    return results
