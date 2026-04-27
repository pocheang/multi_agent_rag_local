def rrf_score(rank: int, k: int) -> float:
    """Calculate Reciprocal Rank Fusion score."""
    return 1.0 / (k + rank)


def hybrid_weights(settings) -> tuple[float, float]:
    """Get normalized vector and BM25 weights from settings."""
    vector_weight = float(getattr(settings, "hybrid_vector_weight", 0.95) or 0.95)
    bm25_weight = float(getattr(settings, "hybrid_bm25_weight", 0.05) or 0.05)
    total = vector_weight + bm25_weight
    if total <= 0:
        return 0.95, 0.05
    return vector_weight / total, bm25_weight / total
