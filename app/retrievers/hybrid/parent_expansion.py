from app.retrievers.parent_store import get_parent_text_map


def expand_to_parent_context(candidates: list[dict]) -> list[dict]:
    """Expand child chunks to parent context while deduplicating."""
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
                        updated = dict(item)
                        updated["child_text"] = item.get("text", "")
                        if parent_map.get(parent_id):
                            updated["text"] = parent_map[parent_id]
                            metadata["context_granularity"] = "parent"
                        else:
                            metadata["context_granularity"] = "child"
                        updated["metadata"] = metadata
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
