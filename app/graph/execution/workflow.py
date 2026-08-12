import threading

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    adaptive_planner_node,
    entry_decider_node,
    graph_decider_node,
    graph_node,
    react_node,
    route_by_next_step,
    router_node,
    synthesis_node,
    vector_decider_node,
    web_node,
)
from app.graph.nodes import (
    vector_node as _vector_node_impl,
)
from app.graph.routing import route_after_graph, route_after_vector
from app.graph.execution.state import GraphState
from app.services.observability.agent_execution_tracker import get_tracker, track_agent_execution
from app.services.observability.tracing import traced_span

_WORKFLOW_LOCK = threading.Lock()
_WORKFLOW_APP = None


def vector_node(state: GraphState) -> GraphState:
    """Vector node wrapper - passes through to implementation."""
    execution_id = state.get("execution_id")
    if execution_id:
        return _tracked_vector_node(state, execution_id=execution_id)
    return _tracked_vector_node(state)


@track_agent_execution(agent_name="router")
def _tracked_router_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return router_node(state)


@track_agent_execution(agent_name="adaptive_planner")
def _tracked_adaptive_planner_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return adaptive_planner_node(state)


@track_agent_execution(agent_name="entry_decider")
def _tracked_entry_decider_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return entry_decider_node(state)


@track_agent_execution(agent_name="vector")
def _tracked_vector_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return _vector_node_impl(state)


@track_agent_execution(agent_name="vector_decider")
def _tracked_vector_decider_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return vector_decider_node(state)


@track_agent_execution(agent_name="graph")
def _tracked_graph_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return graph_node(state)


@track_agent_execution(agent_name="graph_decider")
def _tracked_graph_decider_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return graph_decider_node(state)


@track_agent_execution(agent_name="web")
def _tracked_web_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return web_node(state)


@track_agent_execution(agent_name="synthesis")
def _tracked_synthesis_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return synthesis_node(state)


@track_agent_execution(agent_name="react")
def _tracked_react_node(state: GraphState, execution_id: str | None = None) -> GraphState:
    return react_node(state)


def _wrap_node_with_tracking(node_fn, node_name: str):
    """Wrapper that extracts execution_id from state and passes it to tracked node."""

    def wrapper(state: GraphState) -> GraphState:
        execution_id = state.get("execution_id")
        if execution_id:
            return node_fn(state, execution_id=execution_id)
        return node_fn(state)

    return wrapper


def build_workflow():
    graph = StateGraph(GraphState)
    graph.add_node("router", _wrap_node_with_tracking(_tracked_router_node, "router"))
    graph.add_node("adaptive_planner", _wrap_node_with_tracking(_tracked_adaptive_planner_node, "adaptive_planner"))
    graph.add_node("entry_decider", _wrap_node_with_tracking(_tracked_entry_decider_node, "entry_decider"))
    graph.add_node("vector", vector_node)
    graph.add_node("vector_decider", _wrap_node_with_tracking(_tracked_vector_decider_node, "vector_decider"))
    graph.add_node("graph", _wrap_node_with_tracking(_tracked_graph_node, "graph"))
    graph.add_node("graph_decider", _wrap_node_with_tracking(_tracked_graph_decider_node, "graph_decider"))
    graph.add_node("web", _wrap_node_with_tracking(_tracked_web_node, "web"))
    graph.add_node("synthesis", _wrap_node_with_tracking(_tracked_synthesis_node, "synthesis"))
    graph.add_node("react", _wrap_node_with_tracking(_tracked_react_node, "react"))

    graph.add_edge(START, "router")
    graph.add_edge("router", "adaptive_planner")
    graph.add_edge("adaptive_planner", "entry_decider")
    graph.add_conditional_edges(
        "entry_decider",
        route_by_next_step,
        {
            "vector": "vector",
            "graph": "graph",
            "web": "web",
            "synthesis": "synthesis",
            "react": "react",
        },
    )
    graph.add_edge("vector", "vector_decider")
    graph.add_conditional_edges(
        "vector_decider",
        route_by_next_step,
        {"graph": "graph", "web": "web", "synthesis": "synthesis"},
    )
    graph.add_edge("graph", "graph_decider")
    graph.add_conditional_edges("graph_decider", route_by_next_step, {"web": "web", "synthesis": "synthesis"})
    graph.add_edge("web", "synthesis")
    graph.add_edge("synthesis", END)
    graph.add_edge("react", END)

    return graph.compile()


def run_query(
    question: str,
    use_web_fallback: bool = False,
    use_reasoning: bool = False,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    agent_class_hint: str | None = None,
    retrieval_strategy: str | None = None,
    force_language: str = "",
    session_id: str = "",
    execution_id: str | None = None,
    enable_tracking: bool = True,
    user_id: str | None = None,  # æ·»åŠ  user_id å‚æ•°ç”¨äºŽè¿½è¸ª
) -> GraphState:
    global _WORKFLOW_APP
    if _WORKFLOW_APP is None:
        with _WORKFLOW_LOCK:
            if _WORKFLOW_APP is None:
                _WORKFLOW_APP = build_workflow()
    app = _WORKFLOW_APP

    if not question or not isinstance(question, str):
        raise ValueError("question is required and must be a non-empty string")

    tracker = get_tracker() if enable_tracking else None
    if tracker and enable_tracking:
        execution_id = tracker.start_execution(question, execution_id, user_id=user_id, profile="standard")

    try:
        with traced_span("workflow.run_query", {"strategy": str(retrieval_strategy or "default")}):
            result = app.invoke(
                {
                    "question": question,
                    "session_id": session_id,
                    "memory_context": memory_context,
                    "use_web_fallback": use_web_fallback,
                    "use_reasoning": use_reasoning,
                    "allowed_sources": allowed_sources,
                    "agent_class_hint": agent_class_hint,
                    "retrieval_strategy": retrieval_strategy,
                    "force_language": force_language,
                    "execution_id": execution_id,
                }
            )

        if tracker and enable_tracking:
            tracker.complete_execution(execution_id, result)

        return result
    except Exception as e:
        if tracker and enable_tracking:
            tracker.fail_execution(execution_id, str(e))
        raise


def clear_workflow_cache() -> None:
    global _WORKFLOW_APP
    with _WORKFLOW_LOCK:
        _WORKFLOW_APP = None
