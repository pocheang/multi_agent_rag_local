from app.agents.router_agent import decide_route
from app.graph.state import GraphState


def router_node(state: GraphState) -> GraphState:
    hinted = state.get("agent_class_hint")
    if hinted:
        decision = decide_route(
            state["question"],
            use_reasoning=state.get("use_reasoning", True),
            agent_class_hint=hinted,
        )
    else:
        decision = decide_route(state["question"], use_reasoning=state.get("use_reasoning", True))
    return {
        **state,
        "route": decision.route,
        "reason": decision.reason,
        "skill": decision.skill,
        "agent_class": decision.agent_class,
    }
