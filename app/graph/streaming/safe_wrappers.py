"""Safe wrapper functions for agent calls with resilience patterns."""

import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.services.runtime.bulkhead import bulkhead
from app.services.runtime.resilience import CircuitBreakerOpenError, call_with_circuit_breaker
from app.services.retrieval.logger import RetrievalLog, RetrievalLogger
from app.services.runtime.retry_policy import call_with_retry

logger = logging.getLogger(__name__)


def _agent_func(module_name: str, func_name: str):
    module = sys.modules.get(module_name)
    if module is None:
        module = __import__(module_name, fromlist=[func_name])
    return getattr(module, func_name)


def _call_with_supported_kwargs(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TypeError:
        compact = {k: v for k, v in kwargs.items() if v is not None}
        if compact != kwargs:
            try:
                return fn(*args, **compact)
            except TypeError:
                pass
        return fn(*args)


def _log_retrieval(
    *,
    question: str,
    agent_class: str | None,
    route: str,
    allowed_sources: list[str] | None,
    retrieval_time_ms: float,
    retrieved_count: int,
    effective_hit_count: int,
    top_scores: list[float],
    retrieved_sources: list[str],
    has_result: bool,
    error: str | None = None,
) -> None:
    try:
        RetrievalLogger.get_instance().log_retrieval(
            RetrievalLog(
                log_id=str(uuid4()),
                timestamp=datetime.now(UTC),
                question=question,
                agent_class=agent_class or "general",
                route=route,
                filtered_docs_count=len(allowed_sources) if allowed_sources else 0,
                retrieved_count=retrieved_count,
                effective_hit_count=effective_hit_count,
                top_scores=top_scores,
                retrieval_time_ms=retrieval_time_ms,
                total_time_ms=retrieval_time_ms,
                retrieved_sources=retrieved_sources,
                has_result=has_result,
                error=error,
            )
        )
    except Exception as log_error:
        logger.warning("Failed to log streaming retrieval: %s", log_error)


def safe_vector_result(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
    agent_class: str | None = None,
) -> dict[str, Any]:
    """Execute vector RAG with resilience patterns."""
    start_time = time.time()
    try:
        run_vector_rag = _agent_func("app.agents.rag.vector", "run_vector_rag")
        with bulkhead("retrieval"):
            result = call_with_retry(
                "stream.vector_rag",
                lambda: call_with_circuit_breaker(
                    "vector_rag.run",
                    lambda: _call_with_supported_kwargs(
                        run_vector_rag,
                        question,
                        allowed_sources=allowed_sources,
                        retrieval_strategy=retrieval_strategy,
                        agent_class=agent_class,
                    ),
                ),
            )
        retrieval_time_ms = (time.time() - start_time) * 1000
        citations = result.get("citations", [])
        retrieved_count = result.get("retrieved_count", 0)
        effective_hit_count = result.get("effective_hit_count", 0)
        top_scores = []
        for citation in citations[:3]:
            metadata = citation.get("metadata", {})
            score = metadata.get("hybrid_score") or metadata.get("rerank_score") or metadata.get("dense_score") or 0.0
            top_scores.append(float(score))
        retrieved_sources = []
        for citation in citations:
            source = citation.get("source", "")
            if source and source not in retrieved_sources:
                retrieved_sources.append(source)
        _log_retrieval(
            question=question,
            agent_class=agent_class,
            route="vector",
            allowed_sources=allowed_sources,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=retrieved_count,
            effective_hit_count=effective_hit_count,
            top_scores=top_scores,
            retrieved_sources=retrieved_sources,
            has_result=retrieved_count > 0,
        )
        return result
    except CircuitBreakerOpenError:
        run_vector_rag = _agent_func("app.agents.rag.vector", "run_vector_rag")
        result = _call_with_supported_kwargs(
            run_vector_rag,
            question,
            allowed_sources=allowed_sources,
            retrieval_strategy=retrieval_strategy,
            agent_class=agent_class,
        )
        retrieval_time_ms = (time.time() - start_time) * 1000
        citations = result.get("citations", [])
        retrieved_count = result.get("retrieved_count", 0)
        effective_hit_count = result.get("effective_hit_count", 0)
        top_scores = []
        for citation in citations[:3]:
            metadata = citation.get("metadata", {})
            score = metadata.get("hybrid_score") or metadata.get("rerank_score") or metadata.get("dense_score") or 0.0
            top_scores.append(float(score))
        retrieved_sources = []
        for citation in citations:
            source = citation.get("source", "")
            if source and source not in retrieved_sources:
                retrieved_sources.append(source)
        _log_retrieval(
            question=question,
            agent_class=agent_class,
            route="vector",
            allowed_sources=allowed_sources,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=retrieved_count,
            effective_hit_count=effective_hit_count,
            top_scores=top_scores,
            retrieved_sources=retrieved_sources,
            has_result=retrieved_count > 0,
        )
        return result
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")
        retrieval_time_ms = (time.time() - start_time) * 1000
        _log_retrieval(
            question=question,
            agent_class=agent_class,
            route="vector",
            allowed_sources=allowed_sources,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=0,
            effective_hit_count=0,
            top_scores=[],
            retrieved_sources=[],
            has_result=False,
            error=str(e),
        )
        return {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}


def safe_graph_result(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
    retrieved_docs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute graph RAG with resilience patterns."""
    start_time = time.time()
    try:
        run_graph_rag = _agent_func("app.agents.rag.graph", "run_graph_rag")
        with bulkhead("neo4j"):
            result = call_with_retry(
                "stream.graph_rag",
                lambda: call_with_circuit_breaker(
                    "graph_rag.run",
                    lambda: _call_with_supported_kwargs(
                        run_graph_rag,
                        question,
                        allowed_sources=allowed_sources,
                        agent_class=agent_class,
                        retrieved_docs=retrieved_docs,
                    ),
                ),
            )
        retrieval_time_ms = (time.time() - start_time) * 1000
        entities = result.get("entities", [])
        neighbors = result.get("neighbors", [])
        retrieved_sources = []
        for item in entities + neighbors:
            source = item.get("source", "")
            if source and source not in retrieved_sources:
                retrieved_sources.append(source)
        retrieved_count = len(entities) + len(neighbors)
        _log_retrieval(
            question=question,
            agent_class=agent_class,
            route="graph",
            allowed_sources=allowed_sources,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=retrieved_count,
            effective_hit_count=retrieved_count,
            top_scores=[],
            retrieved_sources=retrieved_sources,
            has_result=retrieved_count > 0,
        )
        return result
    except CircuitBreakerOpenError:
        run_graph_rag = _agent_func("app.agents.rag.graph", "run_graph_rag")
        result = _call_with_supported_kwargs(
            run_graph_rag,
            question,
            allowed_sources=allowed_sources,
            agent_class=agent_class,
            retrieved_docs=retrieved_docs,
        )
        retrieval_time_ms = (time.time() - start_time) * 1000
        entities = result.get("entities", [])
        neighbors = result.get("neighbors", [])
        retrieved_sources = []
        for item in entities + neighbors:
            source = item.get("source", "")
            if source and source not in retrieved_sources:
                retrieved_sources.append(source)
        retrieved_count = len(entities) + len(neighbors)
        _log_retrieval(
            question=question,
            agent_class=agent_class,
            route="graph",
            allowed_sources=allowed_sources,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=retrieved_count,
            effective_hit_count=retrieved_count,
            top_scores=[],
            retrieved_sources=retrieved_sources,
            has_result=retrieved_count > 0,
        )
        return result
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")
        retrieval_time_ms = (time.time() - start_time) * 1000
        _log_retrieval(
            question=question,
            agent_class=agent_class,
            route="graph",
            allowed_sources=allowed_sources,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=0,
            effective_hit_count=0,
            top_scores=[],
            retrieved_sources=[],
            has_result=False,
            error=str(e),
        )
        return {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}


def safe_web_result(question: str) -> dict[str, Any]:
    """Execute web research with resilience patterns."""
    start_time = time.time()
    try:
        run_web_research = _agent_func("app.agents.rag.web", "run_web_research")

        def _web_research_call():
            return run_web_research(question)

        def _with_circuit_breaker():
            return call_with_circuit_breaker("web_research.run", _web_research_call)

        with bulkhead("web"):
            result = call_with_retry(
                "stream.web_research",
                _with_circuit_breaker,
            )
        retrieval_time_ms = (time.time() - start_time) * 1000
        citations = result.get("citations", [])
        retrieved_sources = []
        for citation in citations:
            source = citation.get("source", "")
            if source and source not in retrieved_sources:
                retrieved_sources.append(source)
        _log_retrieval(
            question=question,
            agent_class="general",
            route="web",
            allowed_sources=None,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=len(citations),
            effective_hit_count=len(citations),
            top_scores=[],
            retrieved_sources=retrieved_sources,
            has_result=bool(result.get("used")) and bool(citations),
        )
        return result
    except CircuitBreakerOpenError:
        run_web_research = _agent_func("app.agents.rag.web", "run_web_research")
        result = run_web_research(question)
        retrieval_time_ms = (time.time() - start_time) * 1000
        citations = result.get("citations", [])
        retrieved_sources = []
        for citation in citations:
            source = citation.get("source", "")
            if source and source not in retrieved_sources:
                retrieved_sources.append(source)
        _log_retrieval(
            question=question,
            agent_class="general",
            route="web",
            allowed_sources=None,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=len(citations),
            effective_hit_count=len(citations),
            top_scores=[],
            retrieved_sources=retrieved_sources,
            has_result=bool(result.get("used")) and bool(citations),
        )
        return result
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        retrieval_time_ms = (time.time() - start_time) * 1000
        _log_retrieval(
            question=question,
            agent_class="general",
            route="web",
            allowed_sources=None,
            retrieval_time_ms=retrieval_time_ms,
            retrieved_count=0,
            effective_hit_count=0,
            top_scores=[],
            retrieved_sources=[],
            has_result=False,
            error=str(e),
        )
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}
