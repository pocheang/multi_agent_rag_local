"""Compatibility exports for the canonical enhanced graph RAG implementation."""

from app.agents.rag.enhanced_graph import (
    analyze_pdf_quality,
    extract_document_entities,
    get_document_context_for_query,
    run_graph_rag_with_pdf_context,
    should_use_graph_rag,
)

__all__ = [
    "analyze_pdf_quality",
    "extract_document_entities",
    "get_document_context_for_query",
    "run_graph_rag_with_pdf_context",
    "should_use_graph_rag",
]
