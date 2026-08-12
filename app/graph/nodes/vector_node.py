import logging
import time
from concurrent.futures import TimeoutError as FutureTimeoutError

from app.agents.rag.vector import run_vector_rag
from app.core.config import get_settings
from app.graph.nodes.safe_wrappers import safe_graph_result, safe_vector_result
from app.graph.execution.state import GraphState
from app.services.runtime.bulkhead import bulkhead
from app.services.hybrid_executor import HybridExecutorRejectedError, submit_hybrid
from app.services.runtime.request_context import deadline_exceeded, remaining_seconds
from app.services.runtime.resilience import call_with_circuit_breaker
from app.services.runtime.retry_policy import call_with_retry
from app.services.observability.tracing import traced_span

logger = logging.getLogger(__name__)


def _retrieved_docs_from_vector_result(vector_result: dict | None) -> list[dict]:
    docs = []
    for citation in (vector_result or {}).get("citations", []) or []:
        docs.append(
            {
                "content": citation.get("content", ""),
                "metadata": citation.get("metadata", {}) or {},
            }
        )
    return docs


def vector_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "vector_result": {"context": "", "citations": [], "retrieved_count": 0, "timeout": True}}
    route = state.get("route", "vector")
    if route == "hybrid":
        settings = get_settings()
        if settings.graph_rag_enhanced:
            vector_result = safe_vector_result(
                state["question"],
                state.get("allowed_sources"),
                state.get("retrieval_strategy"),
                state.get("agent_class"),
            )
            graph_result = {"context": "", "entities": [], "neighbors": [], "error": "graph_error:Timeout"}
            if deadline_exceeded():
                graph_result["timeout"] = True
            else:
                graph_result = safe_graph_result(
                    state["question"],
                    state.get("allowed_sources"),
                    state.get("agent_class"),
                    retrieved_docs=_retrieved_docs_from_vector_result(vector_result) or None,
                )
            vector_result["hybrid_execution_success"] = not vector_result.get("error")
            graph_result["hybrid_execution_success"] = not graph_result.get("error") and not graph_result.get("timeout")
            graph_result["hybrid_execution_mode"] = "vector_graph_serial"
            return {**state, "vector_result": vector_result, "graph_result": graph_result}
        timeout_s = remaining_seconds()
        if timeout_s is None:
            timeout_s = 15.0
        timeout_s = max(0.1, float(timeout_s))
        deadline = time.monotonic() + timeout_s
        fut_vector = None
        fut_graph = None
        vector_result = {"context": "", "citations": [], "retrieved_count": 0, "error": "vector_error:Timeout"}
        graph_result = {"context": "", "entities": [], "neighbors": [], "error": "graph_error:Timeout"}
        vector_success = False
        graph_success = False
        try:
            fut_vector = submit_hybrid(
                safe_vector_result,
                state["question"],
                state.get("allowed_sources"),
                state.get("retrieval_strategy"),
                state.get("agent_class"),
            )
            fut_graph = submit_hybrid(
                safe_graph_result,
                state["question"],
                state.get("allowed_sources"),
                state.get("agent_class"),
            )
        except HybridExecutorRejectedError:
            if fut_vector is not None:
                fut_vector.cancel()
            if fut_graph is not None:
                fut_graph.cancel()
            return {
                **state,
                "vector_result": {
                    "context": "",
                    "citations": [],
                    "retrieved_count": 0,
                    "error": "vector_error:Overloaded",
                },
                "graph_result": {
                    "context": "",
                    "entities": [],
                    "neighbors": [],
                    "error": "graph_error:Overloaded",
                },
            }
        try:
            left = max(0.1, deadline - time.monotonic())
            vector_result = fut_vector.result(timeout=left)
            vector_success = not vector_result.get("error")
        except FutureTimeoutError:
            fut_vector.cancel()
            vector_result["timeout"] = True
        except Exception as e:
            logger.exception(f"Vector RAG failed for question: {state.get('question', '')}")
            vector_result = {
                "context": "",
                "citations": [],
                "retrieved_count": 0,
                "error": f"vector_error:{type(e).__name__}",
            }
        try:
            left = max(0.1, deadline - time.monotonic())
            graph_result = fut_graph.result(timeout=left)
            graph_success = not graph_result.get("error")
        except FutureTimeoutError:
            fut_graph.cancel()
            graph_result["timeout"] = True
        except Exception as e:
            logger.exception(f"Graph RAG failed for question: {state.get('question', '')}")
            graph_result = {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}

        vector_result["hybrid_execution_success"] = vector_success
        graph_result["hybrid_execution_success"] = graph_success
        return {**state, "vector_result": vector_result, "graph_result": graph_result}
    try:
        with traced_span("workflow.vector_node", {"strategy": str(state.get("retrieval_strategy", "") or "default")}):
            with bulkhead("llm"):
                result = call_with_retry(
                    "workflow.vector_node",
                    lambda: call_with_circuit_breaker(
                        "vector_rag.run",
                        lambda: run_vector_rag(
                            state["question"],
                            allowed_sources=state.get("allowed_sources"),
                            retrieval_strategy=state.get("retrieval_strategy"),
                            agent_class=state.get("agent_class"),
                        ),
                    ),
                )
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {state.get('question', '')}")
        result = {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}
    return {**state, "vector_result": result}
