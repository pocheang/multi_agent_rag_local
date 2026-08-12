from app.agents.synthesizer.generation import synthesize_answer
from app.graph.execution.state import GraphState
from app.services.answer_safety import sanitize_answer
from app.services.citation_grounding import apply_sentence_grounding
from app.services.explainability import build_explainability_report
from app.services.query_intent import is_casual_chat_query, quick_smalltalk_reply
from app.services.runtime.request_context import deadline_exceeded
from app.services.sessions.language import get_language_preference, update_language_history


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
    force_language = state.get("force_language", "")

    answer = synthesize_answer(
        question=state["question"],
        skill_name=state.get("skill", "answer_with_citations"),
        memory_context=memory_context,
        vector_context=vector_context,
        graph_context=graph_context,
        web_context=web_context,
        use_reasoning=state.get("use_reasoning", True),
        force_language=force_language,
        session_id=state.get("session_id", ""),
    )
    # Extract answer text from dict response
    answer_text = answer["answer"] if isinstance(answer, dict) else answer
    detected_language = answer.get("detected_language", "zh") if isinstance(answer, dict) else "zh"

    # Update session language history
    session_id = state.get("session_id", "")
    if session_id:
        update_language_history(session_id, detected_language)

    # Get language preference for the session
    language_preference = get_language_preference(session_id) if session_id else "zh"

    evidence_texts = []
    for c in state.get("vector_result", {}).get("citations", []) or []:
        evidence_texts.append(str(c.get("content", "")))
    for c in state.get("web_result", {}).get("citations", []) or []:
        evidence_texts.append(str(c.get("content", "")))
    evidence_texts.append(graph_context)
    grounded_answer, grounding_report = apply_sentence_grounding(answer=answer_text, evidence_texts=evidence_texts)
    safe_answer, safety_report = sanitize_answer(grounded_answer)
    next_state = {
        **state,
        "answer": safe_answer,
        "detected_language": detected_language,
        "language_preference": language_preference,
        "grounding": grounding_report,
        "answer_safety": safety_report,
    }
    next_state["explainability"] = build_explainability_report(next_state)
    return next_state
