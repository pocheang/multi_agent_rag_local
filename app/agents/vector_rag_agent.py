from pathlib import Path

from app.core.config import get_settings
from app.retrievers.hybrid_retriever import hybrid_search


def run_vector_rag(question: str, allowed_sources: list[str] | None = None) -> dict:
    settings = get_settings()
    if allowed_sources is None:
        results = hybrid_search(question)
    else:
        results = hybrid_search(question, allowed_sources=allowed_sources)
    citations = []
    context_blocks = []

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
                    "retrieval_sources": retrieval_sources,
                },
            }
        )
        context_blocks.append(
            f"[SOURCE: {src}]\n"
            f"[RETRIEVAL: {','.join(retrieval_sources)}]\n"
            f"{chunk}"
        )

    return {
        "context": "\n\n".join(context_blocks),
        "citations": citations,
        "retrieved_count": len(citations),
    }
