"""
Graph RAG Agent - Unified implementation with optional enhancements.

This module provides graph-based retrieval augmented generation with:
- Basic graph lookup (legacy mode)
- Enhanced PDF-aware optimization (default when documents provided)
- Adaptive parameters based on document quality
"""

import logging

from app.core.config import get_settings
from app.retrievers.stores.vector import OwnerScope
from app.services.agent_document_filter import get_sources_by_agent_class
from app.services.observability.log_safety import question_ref

logger = logging.getLogger(__name__)


__all__ = ["run_graph_rag"]


def _run_graph_rag_impl(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
    retrieved_docs: list[dict] | None = None,
    enable_enhancements: bool | None = None,
    *,
    owner: OwnerScope | None,
) -> dict:
    """
    Run Graph RAG with optional PDF-aware enhancements.

    Args:
        question: User query
        allowed_sources: Optional list of allowed document sources
        agent_class: Agent class for automatic document filtering
        retrieved_docs: Retrieved documents for quality analysis (enables enhancements)
        enable_enhancements: Force enable/disable enhancements (default: auto based on config)
        owner: Caller identity for the vector fallback's store-side metadata check.
            Keyword-only and without a default on purpose: every owner leak on this
            path came from an intermediate function that defaulted it to None.

    Returns:
        Dictionary containing:
        - context: Formatted graph context string
        - entities: List of matched entity names
        - neighbors: List of neighbor relationships
        - paths: List of 2-hop paths
        - graph_signal_score: Relevance score (0-1)
        - confidence: Confidence level (high/medium/low) if enhanced
        - pdf_context: PDF analysis results if enhanced
    """
    settings = get_settings()

    # Always honor agent-class filtering, intersecting it with any explicit source scope.
    if agent_class:
        class_sources = get_sources_by_agent_class(agent_class)
        if allowed_sources is None:
            allowed_sources = class_sources
        elif class_sources is not None:
            allowed_set = set(class_sources)
            allowed_sources = [src for src in allowed_sources if src in allowed_set]

    # Determine whether to use enhancements
    should_enhance = enable_enhancements if enable_enhancements is not None else settings.graph_rag_enhanced

    # Enhanced mode is a property of the *lookup* -- better entity normalization,
    # alias matching, relation weighting -- and needs no documents at all.  Documents,
    # when the orchestrator's second retrieval phase supplies them, only refine the
    # quality estimate that picks the result limits.  Requiring them to enter this
    # branch made the entire enhanced path unreachable: the one production caller
    # (`app/knowledge/adapters.py::_retrieve_graph`) has no documents to pass, so
    # `GRAPH_RAG_ENHANCED` was a switch wired to nothing.
    #
    # This branch reaches only graph_lookup_enhanced, never the vector store, so it
    # needs no owner.  Failure and empty results still reach the vector fallback --
    # `GraphRetrievalService.retrieve` applies it to both branches, keyed on whether
    # graph evidence came back rather than on which implementation ran.
    if should_enhance:
        return _run_enhanced_graph_rag(
            question=question,
            allowed_sources=allowed_sources,
            retrieved_docs=retrieved_docs,
        )

    # Fallback to basic implementation
    return _run_basic_graph_rag(
        question=question,
        allowed_sources=allowed_sources,
        owner=owner,
    )


def _run_basic_graph_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    *,
    owner: OwnerScope | None,
) -> dict:
    """
    Basic graph RAG implementation without enhancements.

    This is the legacy implementation using basic graph_lookup.
    Includes validation, error handling, and fallback indicators.
    """
    from app.tools.graph.core import graph_lookup

    try:
        graph_result = graph_lookup(question, allowed_sources=allowed_sources)
    except Exception as e:
        error_type = type(e).__name__

        # Log differently based on error type
        if error_type in {"ServiceUnavailable", "ConnectionError"}:
            logger.warning("Graph lookup unavailable for %s: %s", question_ref(question), error_type)
        else:
            logger.exception("Graph lookup failed for %s", question_ref(question))

        # Fallback to vector RAG when graph fails
        logger.info("Falling back to vector RAG due to graph lookup error")
        return _fallback_to_vector_rag(question, allowed_sources, error_type, owner=owner)

    # Extract results
    entities = graph_result.get("entities", [])
    neighbors = graph_result.get("neighbors", [])
    paths = graph_result.get("paths", [])
    graph_signal_score = float(graph_result.get("graph_signal_score", 0.0) or 0.0)

    # Format context string
    context = _format_graph_context(entities, neighbors, paths)

    # Check if graph returned empty results
    has_results = bool(entities or neighbors or paths)

    result = {
        "context": context,
        "entities": [x.get("entity") for x in entities if x.get("entity")],
        "neighbors": neighbors,
        "paths": paths,
        "graph_signal_score": graph_signal_score,
    }

    # Add fallback indicator if graph has no results
    if not has_results:
        logger.info("Graph RAG returned empty results for %s", question_ref(question))
        logger.info("Falling back to vector RAG due to empty graph results")
        return _fallback_to_vector_rag(question, allowed_sources, "empty_results", owner=owner)

    return result


def _run_enhanced_graph_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieved_docs: list[dict] | None = None,
) -> dict:
    """
    Enhanced graph RAG with PDF-aware optimizations.

    Applies document quality analysis and adaptive parameters for better accuracy.
    """
    from app.agents.rag.enhanced_graph import (
        get_document_context_for_query,
        run_graph_rag_with_pdf_context,
    )

    settings = get_settings()

    # Analyze document quality if documents provided
    pdf_context = None
    if retrieved_docs:
        pdf_context = get_document_context_for_query(question, retrieved_docs)

        # Skip graph lookup if document quality is too low
        if pdf_context["quality_score"] < settings.graph_rag_min_pdf_quality:
            logger.info(
                "Skipping graph RAG for %s due to low PDF quality: %.2f < %.2f",
                question_ref(question),
                pdf_context["quality_score"],
                settings.graph_rag_min_pdf_quality,
            )
            return {
                "context": "",
                "entities": [],
                "neighbors": [],
                "paths": [],
                "graph_signal_score": 0.0,
                "confidence": "low",
                "pdf_context": pdf_context,
                "skipped_reason": "low_quality_documents",
            }

    # Run enhanced graph RAG
    result = run_graph_rag_with_pdf_context(
        question=question,
        retrieved_docs=retrieved_docs,
        allowed_sources=allowed_sources,
    )

    # Attach PDF context if analyzed
    if pdf_context is not None and "pdf_context" not in result:
        result["pdf_context"] = pdf_context

    return result


def _format_graph_context(
    entities: list[dict],
    neighbors: list[dict],
    paths: list[dict],
) -> str:
    """
    Format graph results into a readable context string.

    Args:
        entities: List of entities with relations
        neighbors: List of neighbor relationships
        paths: List of 2-hop paths

    Returns:
        Formatted multi-line context string
    """
    lines = []

    # Format entities and their relations
    for item in entities:
        name = item.get("entity", "")
        if not name:
            continue

        lines.append(f"Entity: {name}")
        for rel in item.get("relations", []):
            if rel.get("other"):
                weight = rel.get("weight", 0)
                lines.append(f"  - {rel.get('relation')} ({weight:.2f}) -> {rel.get('other')}")

    # Format neighbor relationships
    for row in neighbors:
        if row.get("entity") and row.get("relation") and row.get("other"):
            weight = float(row.get("weight", 0))
            lines.append(f"Neighbor: {row['entity']} -[{row['relation']}|{weight:.2f}]- {row['other']}")

    # Format 2-hop paths
    for row in paths:
        if row.get("source") and row.get("middle") and row.get("target"):
            weight = float(row.get("weight", 0))
            lines.append(
                f"Path2Hop: {row['source']} -[{row.get('rel1', '')}]- {row['middle']} "
                f"-[{row.get('rel2', '')}]- {row['target']} | w={weight:.2f}"
            )

    return "\n".join(lines)


def _fallback_to_vector_rag(
    question: str,
    allowed_sources: list[str] | None,
    reason: str,
    *,
    owner: OwnerScope | None,
) -> dict:
    """
    Fallback to vector RAG when graph RAG fails or returns empty results.

    Args:
        question: User query
        allowed_sources: Optional list of allowed document sources
        reason: Reason for fallback (error type or "empty_results")
        owner: Caller identity, forwarded to the store's own metadata check.
            This used to default to None and two of the three call sites relied
            on the default, so the common fallback (Neo4j down, or an empty
            graph result) searched with the source filter alone -- the owner
            clause the store applies as an independent second check was simply
            absent.  Keyword-only and defaultless so that dropping it is a
            TypeError instead of a silent widening.

    Returns:
        Dictionary with vector RAG results and fallback metadata
    """
    from app.agents.rag.vector import run_vector_rag

    logger.info("Executing vector RAG fallback for %s (reason: %s)", question_ref(question), reason)

    try:
        vector_result = run_vector_rag(
            question=question,
            allowed_sources=allowed_sources,
            owner=owner,
        )

        # Add graph RAG metadata to indicate this was a fallback
        return {
            "context": vector_result.get("context", ""),
            "entities": [],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.0,
            "fallback_used": True,
            "fallback_reason": reason,
            "vector_rag_result": vector_result,
        }
    except Exception as e:
        logger.exception("Vector RAG fallback also failed: %s", e)
        return {
            "context": "",
            "entities": [],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.0,
            "fallback_used": True,
            "fallback_reason": reason,
            "fallback_error": str(e),
        }


class GraphRetrievalService:
    """Single graph retrieval implementation with unified vector fallback."""

    def retrieve(
        self,
        question: str,
        *,
        allowed_sources: list[str] | None = None,
        agent_class: str | None = None,
        retrieved_docs: list[dict] | None = None,
        enable_enhancements: bool | None = None,
        owner: OwnerScope | None,
    ) -> dict:
        result = _run_graph_rag_impl(
            question,
            allowed_sources=allowed_sources,
            agent_class=agent_class,
            retrieved_docs=retrieved_docs,
            enable_enhancements=enable_enhancements,
            owner=owner,
        )
        if not result.get("fallback_used") and not self._has_graph_evidence(result):
            fallback_reason = str(result.get("error") or result.get("skipped_reason") or "empty_results")
            fallback = _fallback_to_vector_rag(question, allowed_sources, fallback_reason, owner=owner)
            for key in ("pdf_context", "skipped_reason", "error"):
                if key in result:
                    fallback[key] = result[key]
            result = fallback
        return self._normalize_result(result, allowed_sources=allowed_sources)

    @staticmethod
    def _has_graph_evidence(result: dict) -> bool:
        return bool(result.get("entities") or result.get("neighbors") or result.get("paths"))

    @staticmethod
    def _normalize_result(result: dict, *, allowed_sources: list[str] | None) -> dict:
        normalized = dict(result)
        vector_result = normalized.get("vector_rag_result") or {}
        if normalized.get("fallback_used"):
            citations = list(vector_result.get("citations") or [])
            retrieved_count = int(vector_result.get("retrieved_count", len(citations)) or 0)
            effective_hit_count = int(vector_result.get("effective_hit_count", retrieved_count) or 0)
            diagnostics = dict(vector_result.get("retrieval_diagnostics") or {})
        else:
            citations = list(normalized.get("citations") or [])
            retrieved_count = (
                len(normalized.get("entities") or [])
                + len(normalized.get("neighbors") or [])
                + len(normalized.get("paths") or [])
            )
            effective_hit_count = retrieved_count
            diagnostics = dict(normalized.get("retrieval_diagnostics") or {})
        diagnostics.setdefault("service", "graph")
        diagnostics.setdefault("allowed_sources", list(allowed_sources) if allowed_sources is not None else None)
        normalized["citations"] = citations
        normalized["retrieved_count"] = retrieved_count
        normalized["effective_hit_count"] = effective_hit_count
        normalized["retrieval_diagnostics"] = diagnostics
        normalized["diagnostics"] = diagnostics
        return normalized


def run_graph_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
    retrieved_docs: list[dict] | None = None,
    enable_enhancements: bool | None = None,
    *,
    owner: OwnerScope | None,
) -> dict:
    """Compatibility entry point forwarding to ``GraphRetrievalService``."""
    return GraphRetrievalService().retrieve(
        question,
        allowed_sources=allowed_sources,
        agent_class=agent_class,
        owner=owner,
        retrieved_docs=retrieved_docs,
        enable_enhancements=enable_enhancements,
    )
