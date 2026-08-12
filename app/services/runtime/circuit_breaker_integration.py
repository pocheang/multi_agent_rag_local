"""
Circuit Breaker Integration Examples for Critical Paths.

This module demonstrates how to integrate circuit breakers into critical
paths like LLM API calls, vector retrieval, and external services.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

from app.services.runtime.resilience import call_with_circuit_breaker, CircuitBreakerOpenError

T = TypeVar("T")


# ============================================================================
# Pattern 1: LLM API Calls
# ============================================================================


class LLMClientWithCircuitBreaker:
    """
    LLM client wrapper with circuit breaker protection.

    Prevents cascading failures when LLM API is down or rate-limited.
    """

    def __init__(self, client: Any):
        self.client = client

    def chat_completion(self, messages: list[dict], model: str, **kwargs) -> Any:
        """
        Call LLM with circuit breaker protection.

        Circuit opens after 3 consecutive failures, stays open for 30s.
        """
        try:
            return call_with_circuit_breaker(
                name=f"llm_api_{model}",
                fn=lambda: self.client.chat.completions.create(
                    messages=messages, model=model, **kwargs
                ),
            )
        except CircuitBreakerOpenError:
            # Circuit is open - return cached response or fallback
            return self._get_fallback_response(messages, model)

    def _get_fallback_response(self, messages: list[dict], model: str) -> Any:
        """Fallback when circuit is open."""
        # Option 1: Return cached response
        # Option 2: Use simpler/faster model
        # Option 3: Return error message
        raise RuntimeError(f"LLM service unavailable (circuit open for {model})")


# ============================================================================
# Pattern 2: Vector Store Operations
# ============================================================================


class VectorStoreWithCircuitBreaker:
    """Vector store wrapper with circuit breaker."""

    def __init__(self, vector_store: Any):
        self.vector_store = vector_store

    def similarity_search(self, query: str, k: int = 5, **kwargs) -> list[Any]:
        """
        Search with circuit breaker protection.

        Falls back to BM25 if vector store circuit opens.
        """
        try:
            return call_with_circuit_breaker(
                name="chroma_search",
                fn=lambda: self.vector_store.similarity_search(query, k=k, **kwargs),
            )
        except CircuitBreakerOpenError:
            # Fallback to BM25-only retrieval
            return self._bm25_fallback(query, k)

    def _bm25_fallback(self, query: str, k: int) -> list[Any]:
        """Fallback to BM25 when vector store is unavailable."""
        from app.retrievers.bm25_retriever import bm25_search

        return bm25_search(query, top_k=k)


# ============================================================================
# Pattern 3: Neo4j Graph Operations
# ============================================================================


class Neo4jClientWithCircuitBreaker:
    """Neo4j client wrapper with circuit breaker."""

    def __init__(self, driver: Any):
        self.driver = driver

    def execute_query(self, cypher: str, parameters: dict | None = None) -> list[dict]:
        """
        Execute Cypher query with circuit breaker.

        Falls back to vector-only retrieval if graph is unavailable.
        """
        try:
            return call_with_circuit_breaker(
                name="neo4j_query",
                fn=lambda: self._run_query(cypher, parameters or {}),
            )
        except CircuitBreakerOpenError:
            # Graph unavailable - return empty results
            # Let caller handle fallback
            return []

    def _run_query(self, cypher: str, parameters: dict) -> list[dict]:
        """Internal query execution."""
        with self.driver.session() as session:
            result = session.run(cypher, parameters)
            return [record.data() for record in result]


# ============================================================================
# Pattern 4: Decorator for Circuit Breaker
# ============================================================================


def with_circuit_breaker(name: str, fallback: Callable | None = None):
    """
    Decorator to add circuit breaker to any function.

    Args:
        name: Circuit breaker name (unique identifier)
        fallback: Optional fallback function to call when circuit is open

    Example:
        @with_circuit_breaker("embedding_service", fallback=lambda x: [0.0] * 768)
        def get_embedding(text: str) -> list[float]:
            return expensive_embedding_call(text)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return call_with_circuit_breaker(name, lambda: func(*args, **kwargs))
            except CircuitBreakerOpenError:
                if fallback:
                    return fallback(*args, **kwargs)
                raise

        return wrapper

    return decorator


# ============================================================================
# Pattern 5: Web Research with Circuit Breaker
# ============================================================================


class WebResearchWithCircuitBreaker:
    """Web research agent with circuit breaker for external API."""

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        """
        Search web with circuit breaker protection.

        Falls back to local knowledge if web search fails.
        """
        try:
            return call_with_circuit_breaker(
                name="duckduckgo_api", fn=lambda: self._search_web(query, max_results)
            )
        except CircuitBreakerOpenError:
            # Web search unavailable - return empty to trigger local fallback
            return []

    def _search_web(self, query: str, max_results: int) -> list[dict]:
        """Internal web search implementation."""
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results


# ============================================================================
# Integration Examples
# ============================================================================


# Example 1: In EnhancedRouterAgent
def integrate_into_router_agent():
    """
    Example: Integrate circuit breaker into router agent.
    """
    from app.core.logging_config import get_logger

    logger = get_logger(__name__)

    class EnhancedRouterAgent:
        def __init__(self, llm_client: Any):
            self.llm = LLMClientWithCircuitBreaker(llm_client)

        def route_query(self, query: str) -> dict:
            try:
                # Call LLM with circuit breaker protection
                response = self.llm.chat_completion(
                    messages=[{"role": "user", "content": f"Route this query: {query}"}],
                    model="gpt-4",
                )
                return self._parse_routing_decision(response)

            except RuntimeError as e:
                if "circuit open" in str(e):
                    logger.warning("llm_circuit_open", fallback="rule_based")
                    # Fallback to rule-based routing
                    return self._rule_based_routing(query)
                raise


# Example 2: In HybridRetriever
def integrate_into_retriever():
    """
    Example: Integrate circuit breaker into hybrid retriever.
    """

    class HybridRetriever:
        def __init__(self, vector_store: Any, bm25_store: Any):
            self.vector = VectorStoreWithCircuitBreaker(vector_store)
            self.bm25 = bm25_store

        def retrieve(self, query: str, top_k: int = 10) -> list[Any]:
            # Vector search with circuit breaker
            vector_results = self.vector.similarity_search(query, k=top_k)

            # BM25 search (no circuit breaker needed - local operation)
            bm25_results = self.bm25.search(query, k=top_k)

            # Fusion
            return self._rrf_fusion(vector_results, bm25_results)


# Example 3: In GraphRAGAgent
def integrate_into_graph_rag():
    """
    Example: Integrate circuit breaker into Graph RAG agent.
    """

    class GraphRAGAgent:
        def __init__(self, neo4j_driver: Any, vector_fallback: Any):
            self.graph = Neo4jClientWithCircuitBreaker(neo4j_driver)
            self.vector_fallback = vector_fallback

        def retrieve(self, query: str, entities: list[str]) -> list[dict]:
            # Try graph retrieval with circuit breaker
            cypher = self._build_cypher_query(entities)
            graph_results = self.graph.execute_query(cypher)

            if not graph_results:
                # Fallback to vector retrieval
                return self.vector_fallback.retrieve(query)

            return graph_results


# ============================================================================
# Monitoring and Observability
# ============================================================================


def get_circuit_breaker_metrics() -> dict[str, Any]:
    """
    Get circuit breaker status for all registered circuits.

    Returns:
        Dictionary with circuit breaker states and failure counts
    """
    from app.services.runtime.resilience import _BREAKERS

    metrics = {}
    for name, state in _BREAKERS.items():
        metrics[name] = {
            "state": "open" if state.opened_until > 0 else "closed",
            "failures": state.fails,
            "opened_until": state.opened_until,
        }
    return metrics


# Example: Expose metrics endpoint
"""
# In app/api/routes/health.py

@router.get("/circuit-breakers")
def circuit_breaker_status():
    from app.services.runtime.circuit_breaker_integration import get_circuit_breaker_metrics

    return get_circuit_breaker_metrics()
"""

