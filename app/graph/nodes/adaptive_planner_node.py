from app.graph.state import GraphState
from app.services.adaptive_rag_policy import build_adaptive_plan
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

    # Preserve router's decision unless adaptive planner has strong reason to override
    final_route = initial_route

    if initial_route == "vector":
        if plan.route == "hybrid":
            final_route = "hybrid"
        elif plan.route == "graph" and plan.prefer_graph:
            final_route = "graph"
    elif initial_route == "graph":
        if plan.route == "hybrid":
            final_route = "hybrid"

    reason_parts = [state.get("reason", "")]
    if final_route != initial_route:
        reason_parts.append(f"adaptive_override: {initial_route}->{final_route}")
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
