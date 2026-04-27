import logging
from concurrent.futures import TimeoutError as FutureTimeoutError
import time
import threading
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.graph_rag_agent import run_graph_rag
from app.agents.router_agent import decide_route
from app.agents.synthesis_agent import synthesize_answer
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.web_research_agent import run_web_research
from app.services.adaptive_rag_policy import build_adaptive_plan
from app.services.answer_safety import sanitize_answer
from app.services.bulkhead import bulkhead
from app.services.citation_grounding import apply_sentence_grounding
from app.services.evidence_scoring import evidence_is_sufficient
from app.services.explainability import build_explainability_report
from app.services.hybrid_executor import HybridExecutorRejectedError, submit_hybrid
from app.services.query_intent import is_casual_chat_query, quick_smalltalk_reply, should_force_web_research
from app.services.request_context import deadline_exceeded, remaining_seconds
from app.services.retry_policy import call_with_retry
from app.services.resilience import call_with_circuit_breaker
from app.services.tracing import traced_span

logger = logging.getLogger(__name__)
_WORKFLOW_LOCK = threading.Lock()
_WORKFLOW_APP = None


class GraphState(TypedDict, total=False):
    question: str
    memory_context: str
    use_web_fallback: bool
    use_reasoning: bool
    route: str
    adaptive_level: str
    adaptive_min_vector_hits: int
    adaptive_prefer_graph: bool
    adaptive_prefer_web: bool
    reason: str
    skill: str
    agent_class: str
    vector_result: dict[str, Any]
    graph_result: dict[str, Any]
    web_result: dict[str, Any]
    answer: str
    grounding: dict[str, Any]
    answer_safety: dict[str, Any]
    explainability: dict[str, Any]
    allowed_sources: list[str]
    agent_class_hint: str | None
    next_step: str
    retrieval_strategy: str | None


def _safe_vector_result(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
) -> dict[str, Any]:
    try:
        with traced_span("workflow.vector_retrieval", {"component": "vector_rag"}):
            with bulkhead("llm"):
                return call_with_retry(
                    "workflow.vector_rag",
                    lambda: call_with_circuit_breaker(
                        "vector_rag.run",
                        lambda: run_vector_rag(
                            question,
                            allowed_sources=allowed_sources,
                            retrieval_strategy=retrieval_strategy,
                        )
                        if retrieval_strategy
                        else run_vector_rag(question, allowed_sources=allowed_sources),
                    ),
                )
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")
        return {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}


def _safe_graph_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    try:
        with bulkhead("neo4j"):
            return call_with_retry(
                "workflow.graph_rag",
                lambda: call_with_circuit_breaker(
                    "graph_rag.run",
                    lambda: run_graph_rag(question, allowed_sources=allowed_sources),
                ),
            )
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")
        return {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}


def _safe_web_result(question: str) -> dict[str, Any]:
    try:
        with bulkhead("web"):
            return call_with_retry(
                "workflow.web_research",
                lambda: call_with_circuit_breaker("web_research.run", lambda: run_web_research(question)),
            )
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}


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
    # Route upgrade rules:
    # 1. vector -> hybrid: allowed if complexity is high
    # 2. vector -> graph: allowed if prefer_graph is set
    # 3. graph -> hybrid: allowed if complexity is high
    # 4. Never downgrade (hybrid/graph -> vector)
    final_route = initial_route

    if initial_route == "vector":
        if plan.route == "hybrid":
            final_route = "hybrid"
        elif plan.route == "graph" and plan.prefer_graph:
            final_route = "graph"
    elif initial_route == "graph":
        if plan.route == "hybrid":
            final_route = "hybrid"
        # graph stays graph if plan suggests vector (no downgrade)
    # initial_route == "hybrid" stays hybrid (no downgrade)

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


def vector_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "vector_result": {"context": "", "citations": [], "retrieved_count": 0, "timeout": True}}
    route = state.get("route", "vector")
    if route == "hybrid":
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
                _safe_vector_result,
                state["question"],
                state.get("allowed_sources"),
                state.get("retrieval_strategy"),
            )
            fut_graph = submit_hybrid(_safe_graph_result, state["question"], state.get("allowed_sources"))
        except HybridExecutorRejectedError:
            # Cancel both futures if submission fails
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
            vector_result = {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}
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

        # Mark hybrid execution status for routing decisions
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
                        ),
                    ),
                )
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {state.get('question', '')}")
        result = {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}
    return {**state, "vector_result": result}


def graph_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "graph_result": {"context": "", "entities": [], "neighbors": [], "timeout": True}}
    return {**state, "graph_result": _safe_graph_result(state["question"], allowed_sources=state.get("allowed_sources"))}


def web_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        return {**state, "web_result": {"used": False, "citations": [], "context": "", "timeout": True}}
    return {**state, "web_result": _safe_web_result(state["question"])}


def synthesis_node(state: GraphState) -> GraphState:
    if deadline_exceeded():
        timeout_answer = "请求超时，请缩小问题范围后重试。"
        next_state = {
            **state,
            "answer": timeout_answer,
            "grounding": {},
            "answer_safety": {},
            "vector_result": state.get("vector_result", {}),
            "graph_result": state.get("graph_result", {}),
            "web_result": state.get("web_result", {"used": False, "citations": [], "context": ""}),
        }
        next_state["explainability"] = build_explainability_report(next_state)
        return next_state
    if is_casual_chat_query(state.get("question", "")):
        answer = quick_smalltalk_reply(state.get("question", "")) or "你好，我在。"
        next_state = {
            **state,
            "answer": answer,
            "route": "smalltalk_fast",
            "reason": "smalltalk_fast_path",
            "skill": "smalltalk",
            "vector_result": {"context": "", "citations": [], "retrieved_count": 0, "fast_path": True},
            "graph_result": {"context": "", "entities": [], "neighbors": [], "fast_path": True},
            "web_result": {"used": False, "citations": [], "context": "", "fast_path": True},
            "grounding": {"checked": False, "reason": "smalltalk_fast_path"},
            "answer_safety": {},
        }
        next_state["explainability"] = build_explainability_report(next_state)
        return next_state
    memory_context = state.get("memory_context", "")
    vector_context = state.get("vector_result", {}).get("context", "")
    graph_context = state.get("graph_result", {}).get("context", "")
    web_context = state.get("web_result", {}).get("context", "")

    answer = synthesize_answer(
        question=state["question"],
        skill_name=state.get("skill", "answer_with_citations"),
        memory_context=memory_context,
        vector_context=vector_context,
        graph_context=graph_context,
        web_context=web_context,
        use_reasoning=state.get("use_reasoning", True),
    )
    evidence_texts = []
    for c in state.get("vector_result", {}).get("citations", []) or []:
        evidence_texts.append(str(c.get("content", "")))
    for c in state.get("web_result", {}).get("citations", []) or []:
        evidence_texts.append(str(c.get("content", "")))
    evidence_texts.append(graph_context)
    grounded_answer, grounding_report = apply_sentence_grounding(answer=answer, evidence_texts=evidence_texts)
    safe_answer, safety_report = sanitize_answer(grounded_answer)
    next_state = {**state, "answer": safe_answer, "grounding": grounding_report, "answer_safety": safety_report}
    next_state["explainability"] = build_explainability_report(next_state)
    return next_state


def route_after_router(state: GraphState):
    if is_casual_chat_query(state.get("question", "")):
        return "synthesis"
    route = state.get("route", "vector")
    if route == "graph":
        return "graph"
    if route == "hybrid":
        return "vector"
    return "vector"


def route_after_vector(state: GraphState):
    if deadline_exceeded():
        return "synthesis"
    question = state.get("question", "")
    if is_casual_chat_query(question):
        return "synthesis"
    route = state.get("route", "vector")
    use_web = state.get("use_web_fallback", True)

    # For hybrid route, both vector and graph are already executed in parallel
    if route == "hybrid":
        vector_result = state.get("vector_result", {})
        graph_result = state.get("graph_result", {})

        # Check if both executions failed or timed out
        vector_failed = vector_result.get("error") or vector_result.get("timeout")
        graph_failed = graph_result.get("error") or graph_result.get("timeout")

        # If both failed, skip evidence check and go to web or synthesis
        if vector_failed and graph_failed:
            if use_web:
                return "web"
            return "synthesis"

        # Normal evidence sufficiency check
        if graph_result:
            min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
            if (not evidence_is_sufficient(vector_result, graph_result, route="hybrid", min_hits=min_hits)) and use_web:
                return "web"
            return "synthesis"
        # This should not happen in normal flow, but fallback to synthesis if missing
        logger.warning("Hybrid route missing graph_result, falling back to synthesis")
        return "synthesis"

    # For vector-only route, check if we need web fallback or graph
    if route == "vector":
        vector_result = state.get("vector_result", {})

        # If vector failed, decide next step based on preferences
        if vector_result.get("error") or vector_result.get("timeout"):
            if state.get("adaptive_prefer_graph", False):
                return "graph"
            if use_web:
                return "web"
            return "synthesis"

        # Prefer web over graph if explicitly set
        if use_web and state.get("adaptive_prefer_web", False):
            return "web"

        # Check if we should go to graph for additional evidence
        if state.get("adaptive_prefer_graph", False):
            return "graph"

        # Check evidence sufficiency
        min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
        if (not evidence_is_sufficient(vector_result, {}, route="vector", min_hits=min_hits)) and use_web:
            return "web"
        return "synthesis"

    # For graph route, go to graph node
    if route == "graph":
        return "graph"

    return "synthesis"


def route_after_graph(state: GraphState):
    if deadline_exceeded():
        return "synthesis"
    question = state.get("question", "")
    if is_casual_chat_query(question):
        return "synthesis"
    route = state.get("route", "graph")
    use_web = state.get("use_web_fallback", True)

    # Check if web is preferred
    if use_web and state.get("adaptive_prefer_web", False):
        return "web"

    graph_result = state.get("graph_result", {})
    min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)

    # For graph-only route, check graph evidence sufficiency
    if (not evidence_is_sufficient({}, graph_result, route="graph", min_hits=min_hits)) and use_web:
        return "web"

    return "synthesis"


def build_workflow():
    graph = StateGraph(GraphState)
    graph.add_node("router", router_node)
    graph.add_node("adaptive_planner", adaptive_planner_node)
    graph.add_node("entry_decider", entry_decider_node)
    graph.add_node("vector", vector_node)
    graph.add_node("vector_decider", vector_decider_node)
    graph.add_node("graph", graph_node)
    graph.add_node("graph_decider", graph_decider_node)
    graph.add_node("web", web_node)
    graph.add_node("synthesis", synthesis_node)

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

    return graph.compile()


def run_query(
    question: str,
    use_web_fallback: bool = False,
    use_reasoning: bool = False,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    agent_class_hint: str | None = None,
    retrieval_strategy: str | None = None,
) -> GraphState:
    global _WORKFLOW_APP
    if _WORKFLOW_APP is None:
        with _WORKFLOW_LOCK:
            if _WORKFLOW_APP is None:
                _WORKFLOW_APP = build_workflow()
    app = _WORKFLOW_APP

    # Validate required fields
    if not question or not isinstance(question, str):
        raise ValueError("question is required and must be a non-empty string")

    with traced_span("workflow.run_query", {"strategy": str(retrieval_strategy or "default")}):
        return app.invoke(
            {
                "question": question,
                "memory_context": memory_context,
                "use_web_fallback": use_web_fallback,
                "use_reasoning": use_reasoning,
                "allowed_sources": allowed_sources,
                "agent_class_hint": agent_class_hint,
                "retrieval_strategy": retrieval_strategy,
            }
        )


def clear_workflow_cache() -> None:
    global _WORKFLOW_APP
    with _WORKFLOW_LOCK:
        _WORKFLOW_APP = None
