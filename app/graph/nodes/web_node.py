from app.graph.nodes.safe_wrappers import safe_web_result
from app.graph.state import GraphState
from app.services.request_context import deadline_exceeded


def web_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "web_result": {"used": False, "citations": [], "context": "", "timeout": True}}
    return {**state, "web_result": safe_web_result(state["question"])}
