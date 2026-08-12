from app.graph.execution.state import GraphState
from app.services.retrieval.adaptive_policy import build_adaptive_plan
from app.services.query_intent import should_force_web_research


def adaptive_planner_node(state: GraphState) -> GraphState:
    force_web = should_force_web_research(state["question"]) or state.get("skill") == "web_fact_check"
    initial_route = state.get("route", "vector")
    plan = build_adaptive_plan(
        question=state["question"],
        initial_route=initial_route,
        skill=state.get("skill", "answer_with_citations"),
        use_web_fallback=state.get("use_web_fallback", True),
        force_web=force_web,
    )

    # Adaptive planning may tune retrieval thresholds and fallback preferences,
    # but it must not replace the router's semantic route. Explicit retrieval
    # failures are handled by downstream fallback nodes.
    final_route = initial_route


    reason_parts = [state.get("reason", "")]

    reason_parts.append(plan.reason)
    reason = " | ".join([p for p in reason_parts if p]).strip()

    return {
        **state,
        "route": final_route,
        "adaptive_level": plan.level,
        "adaptive_min_vector_hits": plan.min_vector_hits,
        "adaptive_prefer_graph": plan.prefer_graph,
        "adaptive_prefer_web": plan.prefer_web,
        "reason": reason,
    }
