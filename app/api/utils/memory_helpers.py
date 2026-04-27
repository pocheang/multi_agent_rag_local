"""
Memory-related helper functions for the Multi-Agent Local RAG API.
"""
from typing import Any

from app.core.config import get_settings
from app.services.memory_store import MemoryStore, build_memory_context

settings = get_settings()


def _memory_store_for_user(user: dict[str, Any]) -> MemoryStore:
    """Get the memory store for a user."""
    return MemoryStore(base_dir=settings.sessions_path / user["user_id"] / "_long_memory")


def _memory_signals_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract memory signals from a query result."""
    vector_result = result.get("vector_result", {}) or {}
    web_result = result.get("web_result", {}) or {}
    vector_citations = vector_result.get("citations", []) or []
    web_citations = web_result.get("citations", []) or []
    return {
        "vector_retrieved": int(vector_result.get("retrieved_count", 0) or 0),
        "vector_effective_hits": int(vector_result.get("effective_hit_count", 0) or 0),
        "citation_count": len(vector_citations) + len(web_citations),
        "web_used": bool(web_result.get("used", False)),
        "route": str(result.get("route", "unknown")),
        "reason": str(result.get("reason", "")),
        "retrieval_diagnostics": vector_result.get("retrieval_diagnostics", {}),
        "grounding": result.get("grounding", {}),
        "explainability": result.get("explainability", {}),
        "answer_safety": result.get("answer_safety", {}),
    }


def _build_memory_context_for_session(user: dict[str, Any], session_id: str | None, question: str, history_store_fn) -> str:
    """Build memory context for a session."""
    if not session_id:
        return ""
    history_store = history_store_fn(user)
    session_data = history_store.get_session(session_id) or {}
    messages = session_data.get("messages", []) or []
    long_term = _memory_store_for_user(user).list_long_term(session_id)
    return build_memory_context(question=question, session_messages=messages, long_term_memories=long_term)


def _promote_long_term_memory(user: dict[str, Any], session_id: str | None, question: str, result: dict[str, Any]) -> None:
    """Promote a query result to long-term memory."""
    if not session_id:
        return
    _memory_store_for_user(user).add_candidate(
        session_id=session_id,
        question=question,
        answer=result.get("answer", ""),
        signals=_memory_signals_from_result(result),
    )
