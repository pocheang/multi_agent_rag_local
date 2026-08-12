"""
ReAct node for LangGraph workflow.
"""

import logging

from app.agents.tool.react import run_react_agent
from app.graph.execution.state import GraphState
from app.services.answer_safety import sanitize_answer
from app.services.runtime.bulkhead import bulkhead
from app.services.citation_grounding import apply_sentence_grounding
from app.services.explainability import build_explainability_report
from app.services.runtime.request_context import deadline_exceeded
from app.services.runtime.retry_policy import call_with_retry
from app.services.sessions.language import get_language_preference, update_language_history
from app.services.observability.tracing import traced_span

logger = logging.getLogger(__name__)


def _default_vector_result() -> dict:
    return {"context": "", "citations": [], "retrieved_count": 0, "effective_hit_count": 0}


def _default_graph_result() -> dict:
    return {"context": "", "entities": [], "neighbors": [], "paths": []}


def _default_web_result() -> dict:
    return {"used": False, "citations": [], "context": ""}


def _build_evidence_texts(vector_result: dict, graph_result: dict, web_result: dict) -> list[str]:
    evidence_texts: list[str] = []
    for citation in vector_result.get("citations", []) or []:
        evidence_texts.append(str(citation.get("content", "")))
    for citation in web_result.get("citations", []) or []:
        evidence_texts.append(str(citation.get("content", "")))
    evidence_texts.append(str(graph_result.get("context", "") or ""))
    return evidence_texts


def _finalize_state(
    state: GraphState,
    *,
    answer: str,
    detected_language: str,
    vector_result: dict,
    graph_result: dict,
    web_result: dict,
    react_result: dict,
    grounding: dict,
    answer_safety: dict,
) -> GraphState:
    session_id = state.get("session_id", "")
    if session_id and detected_language:
        update_language_history(session_id, detected_language)
    language_preference = (
        get_language_preference(session_id) if session_id else (state.get("force_language", "") or detected_language)
    )

    next_state: GraphState = {
        **state,
        "route": state.get("route", "react"),
        "answer": answer,
        "detected_language": detected_language,
        "language_preference": language_preference,
        "vector_result": vector_result,
        "graph_result": graph_result,
        "web_result": web_result,
        "react_result": react_result,
        "grounding": grounding,
        "answer_safety": answer_safety,
    }
    next_state["explainability"] = build_explainability_report(next_state)
    return next_state


def react_node(state: GraphState) -> GraphState:
    """Execute ReAct agent and return the standard workflow payload."""
    default_vector = _default_vector_result()
    default_graph = _default_graph_result()
    default_web = _default_web_result()

    if deadline_exceeded():
        logger.warning("Deadline exceeded before ReAct execution")
        return _finalize_state(
            state,
            answer="抱歉，处理超时。请稍后重试。",
            detected_language=state.get("force_language", "") or "zh",
            vector_result=default_vector,
            graph_result=default_graph,
            web_result=default_web,
            react_result={"error": "deadline_exceeded", "iterations_used": 0},
            grounding={},
            answer_safety={},
        )

    question = state.get("question", "")
    if not question:
        logger.error("No question provided to react_node")
        return _finalize_state(
            state,
            answer="错误：未提供问题。",
            detected_language=state.get("force_language", "") or "zh",
            vector_result=default_vector,
            graph_result=default_graph,
            web_result=default_web,
            react_result={"error": "no_question"},
            grounding={},
            answer_safety={},
        )

    try:
        with traced_span("workflow.react_node", {"question_length": len(question)}):
            with bulkhead("llm"):
                result = call_with_retry(
                    "workflow.react_node",
                    lambda: run_react_agent(
                        question=question,
                        memory_context=state.get("memory_context", ""),
                        allowed_sources=state.get("allowed_sources"),
                        retrieval_strategy=state.get("retrieval_strategy"),
                        agent_class=state.get("agent_class"),
                        use_reasoning=state.get("use_reasoning", False),
                        max_iterations=5,
                        force_language=state.get("force_language", ""),
                        session_id=state.get("session_id", ""),
                    ),
                )

        logger.info(
            "ReAct completed: %s iterations, answer length: %s",
            result.get("iterations_used", 0),
            len(result.get("answer", "")),
        )

        vector_result = result.get("vector_result") or default_vector
        graph_result = result.get("graph_result") or default_graph
        web_result = result.get("web_result") or default_web
        detected_language = result.get("detected_language", state.get("force_language", "") or "zh")
        grounded_answer, grounding_report = apply_sentence_grounding(
            answer=str(result.get("answer", "") or ""),
            evidence_texts=_build_evidence_texts(vector_result, graph_result, web_result),
        )
        safe_answer, safety_report = sanitize_answer(grounded_answer)

        return _finalize_state(
            state,
            answer=safe_answer,
            detected_language=detected_language,
            vector_result=vector_result,
            graph_result=graph_result,
            web_result=web_result,
            react_result={
                "history": result.get("react_history", []),
                "iterations_used": result.get("iterations_used", 0),
                "contexts": result.get("contexts", {}),
            },
            grounding=grounding_report,
            answer_safety=safety_report,
        )

    except Exception as e:
        logger.exception("ReAct agent failed: %s", e)
        return _finalize_state(
            state,
            answer=f"抱歉，ReAct处理失败：{type(e).__name__}",
            detected_language=state.get("force_language", "") or "zh",
            vector_result=default_vector,
            graph_result=default_graph,
            web_result=default_web,
            react_result={
                "error": f"react_error:{type(e).__name__}",
                "error_detail": str(e),
            },
            grounding={},
            answer_safety={},
        )
