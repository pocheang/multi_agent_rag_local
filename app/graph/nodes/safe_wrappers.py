import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.rag.graph import run_graph_rag
from app.agents.rag.vector import run_vector_rag
from app.agents.rag.web import run_web_research
from app.services.runtime.bulkhead import bulkhead
from app.services.runtime.resilience import call_with_circuit_breaker
from app.services.retrieval.logger import RetrievalLog, RetrievalLogger
from app.services.runtime.retry_policy import call_with_retry
from app.services.observability.tracing import traced_span

logger = logging.getLogger(__name__)


def safe_vector_result(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
    agent_class: str | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    try:
        with traced_span("workflow.vector_retrieval", {"component": "vector_rag"}):
            with bulkhead("llm"):
                result = call_with_retry(
                    "workflow.vector_rag",
                    lambda: call_with_circuit_breaker(
                        "vector_rag.run",
                        lambda: run_vector_rag(
                            question,
                            allowed_sources=allowed_sources,
                            retrieval_strategy=retrieval_strategy,
                            agent_class=agent_class,
                        )
                        if retrieval_strategy
                        else run_vector_rag(question, allowed_sources=allowed_sources, agent_class=agent_class),
                    ),
                )

        # Log successful retrieval
        retrieval_time_ms = (time.time() - start_time) * 1000
        try:
            retrieval_logger = RetrievalLogger.get_instance()

            # Extract metrics from result
            citations = result.get("citations", [])
            retrieved_count = result.get("retrieved_count", 0)
            effective_hit_count = result.get("effective_hit_count", 0)

            # Extract top 3 scores from citations
            top_scores = []
            for c in citations[:3]:
                metadata = c.get("metadata", {})
                score = (
                    metadata.get("hybrid_score") or metadata.get("rerank_score") or metadata.get("dense_score") or 0.0
                )
                top_scores.append(float(score))

            # Extract source filenames from citations
            retrieved_sources = []
            for c in citations:
                source = c.get("source", "")
                if source and source not in retrieved_sources:
                    retrieved_sources.append(source)

            retrieval_logger.log_retrieval(
                RetrievalLog(
                    log_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    question=question,
                    agent_class=agent_class or "general",
                    route="vector",
                    filtered_docs_count=len(allowed_sources) if allowed_sources else 0,
                    retrieved_count=retrieved_count,
                    effective_hit_count=effective_hit_count,
                    top_scores=top_scores,
                    retrieval_time_ms=retrieval_time_ms,
                    total_time_ms=retrieval_time_ms,
                    retrieved_sources=retrieved_sources,
                    has_result=retrieved_count > 0,
                    error=None,
                )
            )
        except Exception as log_error:
            logger.warning(f"Failed to log retrieval: {log_error}")

        return result
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")

        # Log failed retrieval
        retrieval_time_ms = (time.time() - start_time) * 1000
        try:
            retrieval_logger = RetrievalLogger.get_instance()
            retrieval_logger.log_retrieval(
                RetrievalLog(
                    log_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    question=question,
                    agent_class=agent_class or "general",
                    route="vector",
                    filtered_docs_count=len(allowed_sources) if allowed_sources else 0,
                    retrieved_count=0,
                    effective_hit_count=0,
                    top_scores=[],
                    retrieval_time_ms=retrieval_time_ms,
                    total_time_ms=retrieval_time_ms,
                    retrieved_sources=[],
                    has_result=False,
                    error=str(e),
                )
            )
        except Exception as log_error:
            logger.warning(f"Failed to log retrieval: {log_error}")

        return {"context": "", "citations": [], "retrieved_count": 0, "effective_hit_count": 0, "retrieval_diagnostics": {}, "diagnostics": {}, "error": f"vector_error:{type(e).__name__}"}


def safe_graph_result(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
    retrieved_docs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    try:
        with bulkhead("neo4j"):
            result = call_with_retry(
                "workflow.graph_rag",
                lambda: call_with_circuit_breaker(
                    "graph_rag.run",
                    lambda: run_graph_rag(
                        question,
                        allowed_sources=allowed_sources,
                        agent_class=agent_class,
                        retrieved_docs=retrieved_docs,
                    ),
                ),
            )

        # Log successful retrieval
        retrieval_time_ms = (time.time() - start_time) * 1000
        try:
            retrieval_logger = RetrievalLogger.get_instance()

            # Extract metrics from result
            entities = result.get("entities", [])
            neighbors = result.get("neighbors", [])
            retrieved_count = len(entities) + len(neighbors)
            effective_hit_count = retrieved_count

            # Extract sources from entities and neighbors
            retrieved_sources = []
            for entity in entities:
                source = entity.get("source", "")
                if source and source not in retrieved_sources:
                    retrieved_sources.append(source)
            for neighbor in neighbors:
                source = neighbor.get("source", "")
                if source and source not in retrieved_sources:
                    retrieved_sources.append(source)

            retrieval_logger.log_retrieval(
                RetrievalLog(
                    log_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    question=question,
                    agent_class=agent_class or "general",
                    route="graph",
                    filtered_docs_count=len(allowed_sources) if allowed_sources else 0,
                    retrieved_count=retrieved_count,
                    effective_hit_count=effective_hit_count,
                    top_scores=[],
                    retrieval_time_ms=retrieval_time_ms,
                    total_time_ms=retrieval_time_ms,
                    retrieved_sources=retrieved_sources,
                    has_result=retrieved_count > 0,
                    error=None,
                )
            )
        except Exception as log_error:
            logger.warning(f"Failed to log retrieval: {log_error}")

        return result
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")

        # Log failed retrieval
        retrieval_time_ms = (time.time() - start_time) * 1000
        try:
            retrieval_logger = RetrievalLogger.get_instance()
            retrieval_logger.log_retrieval(
                RetrievalLog(
                    log_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    question=question,
                    agent_class=agent_class or "general",
                    route="graph",
                    filtered_docs_count=len(allowed_sources) if allowed_sources else 0,
                    retrieved_count=0,
                    effective_hit_count=0,
                    top_scores=[],
                    retrieval_time_ms=retrieval_time_ms,
                    total_time_ms=retrieval_time_ms,
                    retrieved_sources=[],
                    has_result=False,
                    error=str(e),
                )
            )
        except Exception as log_error:
            logger.warning(f"Failed to log retrieval: {log_error}")

        return {"context": "", "entities": [], "neighbors": [], "paths": [], "citations": [], "retrieved_count": 0, "effective_hit_count": 0, "retrieval_diagnostics": {}, "diagnostics": {}, "error": f"graph_error:{type(e).__name__}"}


def safe_web_result(question: str) -> dict[str, Any]:
    try:
        def _web_research_call():
            return run_web_research(question)

        def _with_circuit_breaker():
            return call_with_circuit_breaker("web_research.run", _web_research_call)

        with bulkhead("web"):
            return call_with_retry(
                "workflow.web_research",
                _with_circuit_breaker,
            )
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}
