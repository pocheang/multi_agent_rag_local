from app.graph.routing.route_logic import route_after_router, route_after_vector, route_after_graph
from app.graph.state import GraphState


def entry_decider_node(state: GraphState) -> GraphState:
    return {**state, "next_step": route_after_router(state)}


def vector_decider_node(state: GraphState) -> GraphState:
    return {**state, "next_step": route_after_vector(state)}


def graph_decider_node(state: GraphState) -> GraphState:
    return {**state, "next_step": route_after_graph(state)}


def route_by_next_step(state: GraphState):
    step = str(state.get("next_step", "") or "").strip().lower()
    if step in {"vector", "graph", "web", "synthesis"}:
        return step
    return "synthesis"
