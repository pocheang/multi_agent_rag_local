from app.graph.nodes.safe_wrappers import safe_graph_result
from app.graph.state import GraphState
from app.services.request_context import deadline_exceeded


def graph_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "graph_result": {"context": "", "entities": [], "neighbors": [], "timeout": True}}
    return {**state, "graph_result": safe_graph_result(state["question"], allowed_sources=state.get("allowed_sources"))}
