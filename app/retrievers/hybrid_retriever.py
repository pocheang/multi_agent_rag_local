from collections import defaultdict

from app.core.config import get_settings
from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.parent_store import get_parent_text_map
from app.retrievers.reranker import rerank
from app.retrievers.vector_store import similarity_search


def _rrf_score(rank: int, k: int) -> float:
    return 1.0 / (k + rank)


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
                        expanded[idx] = item
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


def hybrid_search(query: str, allowed_sources: list[str] | None = None) -> list[dict]:
    settings = get_settings()
    if allowed_sources is None:
        vector_results = similarity_search(query, k=settings.vector_top_k)
        bm25_results = bm25_search(query, k=settings.bm25_top_k)
    else:
        vector_results = similarity_search(query, k=settings.vector_top_k, allowed_sources=allowed_sources)
        bm25_results = bm25_search(query, k=settings.bm25_top_k, allowed_sources=allowed_sources)

    merged: dict[str, dict] = {}
    scores = defaultdict(float)

    for idx, (doc, score) in enumerate(vector_results, start=1):
        metadata = dict(doc.metadata)
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
        scores[item_id] += _rrf_score(idx, settings.hybrid_rrf_k)

    for idx, item in enumerate(bm25_results, start=1):
        item_id = item["id"]
        existing = merged.get(item_id)
        if existing:
            if "bm25" not in existing["retrieval_sources"]:
                existing["retrieval_sources"].append("bm25")
            existing["bm25_score"] = item.get("bm25_score", 0.0)
        else:
            merged[item_id] = {
                "id": item_id,
                "text": item["text"],
                "metadata": item.get("metadata", {}),
                "bm25_score": item.get("bm25_score", 0.0),
                "retrieval_sources": ["bm25"],
            }
        scores[item_id] += _rrf_score(idx, settings.hybrid_rrf_k)

    fused = []
    for item_id, item in merged.items():
        candidate = dict(item)
        candidate["hybrid_score"] = float(scores[item_id])
        fused.append(candidate)

    fused.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
    reranked = rerank(query, fused, top_n=settings.reranker_top_n)
    return _expand_to_parent_context(reranked)
