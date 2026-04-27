import logging

from app.graph.state import GraphState
from app.services.evidence_scoring import evidence_is_sufficient
from app.services.query_intent import is_casual_chat_query
from app.services.request_context import deadline_exceeded

logger = logging.getLogger(__name__)


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

    if route == "hybrid":
        vector_result = state.get("vector_result", {})
        graph_result = state.get("graph_result", {})

        vector_failed = vector_result.get("error") or vector_result.get("timeout")
        graph_failed = graph_result.get("error") or graph_result.get("timeout")

        if vector_failed and graph_failed:
            if use_web:
                return "web"
            return "synthesis"

        if graph_result:
            min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
            if (not evidence_is_sufficient(vector_result, graph_result, route="hybrid", min_hits=min_hits)) and use_web:
                return "web"
            return "synthesis"
        logger.warning("Hybrid route missing graph_result, falling back to synthesis")
        return "synthesis"

    if route == "vector":
        vector_result = state.get("vector_result", {})

        if vector_result.get("error") or vector_result.get("timeout"):
            if state.get("adaptive_prefer_graph", False):
                return "graph"
            if use_web:
                return "web"
            return "synthesis"

        if use_web and state.get("adaptive_prefer_web", False):
            return "web"

        if state.get("adaptive_prefer_graph", False):
            return "graph"

        min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
        if (not evidence_is_sufficient(vector_result, {}, route="vector", min_hits=min_hits)) and use_web:
            return "web"
        return "synthesis"

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

    if use_web and state.get("adaptive_prefer_web", False):
        return "web"

    graph_result = state.get("graph_result", {})
    min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)

    if (not evidence_is_sufficient({}, graph_result, route="graph", min_hits=min_hits)) and use_web:
        return "web"

    return "synthesis"
