import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.graph_rag_agent import run_graph_rag
from app.agents.router_agent import decide_route
from app.agents.synthesis_agent import synthesize_answer
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.web_research_agent import run_web_research
from app.services.query_intent import is_smalltalk_query, should_force_web_research

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    question: str
    memory_context: str
    use_web_fallback: bool
    use_reasoning: bool
    route: str
    reason: str
    skill: str
    agent_class: str
    vector_result: dict[str, Any]
    graph_result: dict[str, Any]
    web_result: dict[str, Any]
    answer: str
    allowed_sources: list[str]


def _safe_vector_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    try:
        return run_vector_rag(question, allowed_sources=allowed_sources)
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")
        return {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}


def _safe_graph_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    try:
        return run_graph_rag(question, allowed_sources=allowed_sources)
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")
        return {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}


def _safe_web_result(question: str) -> dict[str, Any]:
    try:
        return run_web_research(question)
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}


def router_node(state: GraphState) -> GraphState:
    decision = decide_route(state["question"], use_reasoning=state.get("use_reasoning", True))
    return {
        **state,
        "route": decision.route,
        "reason": decision.reason,
        "skill": decision.skill,
        "agent_class": decision.agent_class,
    }


def vector_node(state: GraphState) -> GraphState:
    return {**state, "vector_result": _safe_vector_result(state["question"], allowed_sources=state.get("allowed_sources"))}


def graph_node(state: GraphState) -> GraphState:
    return {**state, "graph_result": _safe_graph_result(state["question"], allowed_sources=state.get("allowed_sources"))}


def web_node(state: GraphState) -> GraphState:
    return {**state, "web_result": _safe_web_result(state["question"])}


def synthesis_node(state: GraphState) -> GraphState:
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
    return {**state, "answer": answer}


def route_after_router(state: GraphState):
    route = state.get("route", "vector")
    if route == "graph":
        return "graph"
    if route == "hybrid":
        return "vector"
    return "vector"


def route_after_vector(state: GraphState):
    question = state.get("question", "")
    if is_smalltalk_query(question):
        return "synthesis"
    route = state.get("route", "vector")
    use_web = state.get("use_web_fallback", True)
    if use_web and (should_force_web_research(question) or state.get("skill") == "web_fact_check"):
        return "web"
    if route == "hybrid":
        return "graph"
    retrieved_count = state.get("vector_result", {}).get("retrieved_count", 0)
    if retrieved_count < 2 and use_web:
        return "web"
    return "synthesis"


def route_after_graph(state: GraphState):
    question = state.get("question", "")
    if is_smalltalk_query(question):
        return "synthesis"
    route = state.get("route", "graph")
    use_web = state.get("use_web_fallback", True)
    if use_web and (should_force_web_research(question) or state.get("skill") == "web_fact_check"):
        return "web"
    has_graph_entities = bool(state.get("graph_result", {}).get("entities", []))
    if route == "hybrid":
        if state.get("vector_result", {}).get("retrieved_count", 0) < 2 and use_web:
            return "web"
        return "synthesis"
    if (not has_graph_entities) and use_web:
        return "web"
    return "synthesis"


def build_workflow():
    graph = StateGraph(GraphState)
    graph.add_node("router", router_node)
    graph.add_node("vector", vector_node)
    graph.add_node("graph", graph_node)
    graph.add_node("web", web_node)
    graph.add_node("synthesis", synthesis_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "vector": "vector",
            "graph": "graph",
        },
    )
    graph.add_conditional_edges("vector", route_after_vector, {"graph": "graph", "web": "web", "synthesis": "synthesis"})
    graph.add_conditional_edges("graph", route_after_graph, {"web": "web", "synthesis": "synthesis"})
    graph.add_edge("web", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()


def run_query(
    question: str,
    use_web_fallback: bool = True,
    use_reasoning: bool = True,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
) -> GraphState:
    app = build_workflow()
    return app.invoke(
        {
            "question": question,
            "memory_context": memory_context,
            "use_web_fallback": use_web_fallback,
            "use_reasoning": use_reasoning,
            "allowed_sources": allowed_sources,
        }
    )
