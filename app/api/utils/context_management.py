"""
API integration utilities for context management.
"""

from app.services.context_management import (
    get_context_service,
)


def process_query_with_context(
    query: str,
    session_id: str,
) -> dict[str, object]:
    """
    Process query with context management.

    Args:
        query: User query
        session_id: Session identifier

    Returns:
        Dictionary with resolved query and context information
    """
    service = get_context_service()
    result = service.process_query(query, session_id)

    return {
        "original_query": result.original,
        "resolved_query": result.resolved,
        "needs_clarification": result.needs_clarification,
        "confidence": result.confidence,
        "entities_resolved": result.entities_resolved,
        "topic_switch": result.topic_switch,
    }


def get_session_context(session_id: str) -> dict[str, object] | None:
    """
    Get current context for a session.

    Args:
        session_id: Session identifier

    Returns:
        Dictionary with context information or None if not found
    """
    service = get_context_service()
    context = service.get_context(session_id)

    if context is None:
        return None

    # Get recent entities
    recent_entities = context.entity_tracker.get_recent_entities(n=5)

    return {
        "session_id": context.session_id,
        "turn_count": context.turn_count,
        "current_topic": context.current_topic,
        "entities": [
            {
                "text": e.text,
                "type": e.type,
                "mention_turn": e.mention_turn,
                "confidence": e.confidence,
            }
            for e in recent_entities
        ],
    }


def clear_session_context(session_id: str) -> None:
    """
    Clear context for a session.

    Args:
        session_id: Session identifier
    """
    service = get_context_service()
    service.clear_context(session_id)
