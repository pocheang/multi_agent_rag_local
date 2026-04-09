from pathlib import Path

from app.core.config import get_settings
from app.retrievers.hybrid_retriever import hybrid_search_with_diagnostics


def run_vector_rag(question: str, allowed_sources: list[str] | None = None, retrieval_strategy: str | None = None) -> dict:
    settings = get_settings()
    try:
        results, diagnostics = hybrid_search_with_diagnostics(
            question,
            allowed_sources=allowed_sources,
            retrieval_strategy=retrieval_strategy,
        )
    except TypeError:
        # Backward-compatible fallback for monkeypatched/stubbed signatures in tests.
        results, diagnostics = hybrid_search_with_diagnostics(
            question,
            allowed_sources=allowed_sources,
        )
    citations = []
    context_blocks = []
    effective_hit_count = 0

    for item in results[: settings.max_context_chunks]:
        metadata = item.get("metadata", {})
        src_full = str(metadata.get("source", "unknown"))
        src = Path(src_full).name if src_full else "unknown"
        chunk = item.get("text", "")[:1200]
        retrieval_sources = item.get("retrieval_sources", [])
        if not isinstance(retrieval_sources, list):
            retrieval_sources = [str(retrieval_sources)]
        citations.append(
            {
                "source": src,
                "content": chunk,
                "metadata": {
                    **metadata,
                    "dense_score": item.get("dense_score"),
                    "bm25_score": item.get("bm25_score"),
                    "hybrid_score": item.get("hybrid_score"),
                    "rerank_score": item.get("rerank_score"),
                    "rank_feature_score": item.get("rank_feature_score"),
                    "retrieval_sources": retrieval_sources,
                },
            }
        )
        context_blocks.append(
            f"[SOURCE: {src}]\n"
            f"[RETRIEVAL: {','.join(retrieval_sources)}]\n"
            f"{chunk}"
        )
        # RAGFlow-style evidence gating: prefer score-backed hits, but keep
        # unknown-score hits valid to avoid over-dropping sparse corpora.
        dense_score = item.get("dense_score")
        bm25_score = item.get("bm25_score")
        rerank_score = item.get("rerank_score")
        if isinstance(rerank_score, (int, float)):
            if float(rerank_score) > 0:
                effective_hit_count += 1
        elif isinstance(dense_score, (int, float)):
            if float(dense_score) >= 0.2:
                effective_hit_count += 1
        elif isinstance(bm25_score, (int, float)):
            if float(bm25_score) > 0:
                effective_hit_count += 1
        else:
            effective_hit_count += 1

    return {
        "context": "\n\n".join(context_blocks),
        "citations": citations,
        "retrieved_count": len(citations),
        "effective_hit_count": effective_hit_count,
        "retrieval_diagnostics": diagnostics,
    }
