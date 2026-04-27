import re


_COMPLEX_HINT_RE = re.compile(
    r"(对比|比较|trade[- ]?off|architecture|timeline|root cause|复盘|多阶段|attack chain)",
    flags=re.IGNORECASE,
)


def adaptive_retrieval_params(query: str, settings, dynamic_enabled: bool) -> tuple[int, int, int]:
    """Dynamically adjust retrieval parameters based on query complexity."""
    vector_top_k = int(getattr(settings, "vector_top_k", 6) or 6)
    bm25_top_k = int(getattr(settings, "bm25_top_k", 6) or 6)
    reranker_top_n = int(getattr(settings, "reranker_top_n", 5) or 5)
    if not dynamic_enabled:
        return vector_top_k, bm25_top_k, reranker_top_n

    q = str(query or "")
    token_count = len(re.findall(r"[A-Za-z0-9_]+|[一-鿿]", q))
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
