"""Safe wrapper functions for agent calls with resilience patterns."""

import logging
from typing import Any

from app.agents.graph_rag_agent import run_graph_rag
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.web_research_agent import run_web_research
from app.services.bulkhead import bulkhead
from app.services.resilience import call_with_circuit_breaker
from app.services.retry_policy import call_with_retry

logger = logging.getLogger(__name__)


def safe_vector_result(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
) -> dict[str, Any]:
    """Execute vector RAG with resilience patterns."""
    try:
        with bulkhead("retrieval"):
            return call_with_retry(
                "stream.vector_rag",
                lambda: call_with_circuit_breaker(
                    "vector_rag.run",
                    lambda: run_vector_rag(
                        question,
                        allowed_sources=allowed_sources,
                        retrieval_strategy=retrieval_strategy,
                    )
                    if retrieval_strategy
                    else run_vector_rag(question, allowed_sources=allowed_sources),
                ),
            )
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")
        return {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}


def safe_graph_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    """Execute graph RAG with resilience patterns."""
    try:
        with bulkhead("neo4j"):
            return call_with_retry(
                "stream.graph_rag",
                lambda: call_with_circuit_breaker(
                    "graph_rag.run",
                    lambda: run_graph_rag(question, allowed_sources=allowed_sources),
                ),
            )
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")
        return {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}


def safe_web_result(question: str) -> dict[str, Any]:
    """Execute web research with resilience patterns."""
    try:
        with bulkhead("web"):
            return call_with_retry(
                "stream.web_research",
                lambda: call_with_circuit_breaker("web_research.run", lambda: run_web_research(question)),
            )
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}
