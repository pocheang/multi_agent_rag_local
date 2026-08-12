from app.graph.nodes.safe_wrappers import safe_graph_result
from app.graph.execution.state import GraphState
from app.services.runtime.request_context import deadline_exceeded


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


def graph_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "graph_result": {"context": "", "entities": [], "neighbors": [], "timeout": True}}
    retrieved_docs = _retrieved_docs_from_vector_result(state.get("vector_result"))
    return {
        **state,
        "graph_result": safe_graph_result(
            state["question"],
            allowed_sources=state.get("allowed_sources"),
            agent_class=state.get("agent_class"),
            retrieved_docs=retrieved_docs or None,
        ),
    }
