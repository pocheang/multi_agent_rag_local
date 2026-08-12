"""Compatibility re-export for :mod:`app.services.context_tracker`.

Task C retains one temporary workflow import. This module owns no context state
or behavior and can be retired after that caller and public test imports move
to the canonical service.
"""

from app.services.context_tracker import (
    _background_cleanup_loop,
    _context_store,
    _detect_intent,
    _detect_reference_pronouns,
    _generate_context_summary,
    _get_top_entities,
    _is_followup_query,
    cleanup_expired_contexts,
    clear_context,
    get_all_sessions,
    get_context,
    get_context_aware_routing_hints,
    get_store_stats,
    resolve_query_with_context,
    start_background_cleanup,
    stop_background_cleanup,
    update_conversation_context,
)
from app.agents.shared.quality_config import (
    CONTEXT_MAX_HISTORY_TURNS,
    CONTEXT_SUMMARY_FREQUENCY,
    CONTEXT_SUMMARY_MIN_TURNS,
    CONTEXT_TTL_SECONDS,
)
from app.agents.shared.quality_models import ConversationContext, ConversationTurn, ContextHints

__all__ = [
    "start_background_cleanup",
    "stop_background_cleanup",
    "update_conversation_context",
    "get_context_aware_routing_hints",
    "resolve_query_with_context",
    "cleanup_expired_contexts",
    "clear_context",
    "get_context",
    "get_all_sessions",
    "get_store_stats",
    "_background_cleanup_loop",
    "_context_store",
    "_detect_intent",
    "_detect_reference_pronouns",
    "_generate_context_summary",
    "_get_top_entities",
    "_is_followup_query",
    "ConversationContext",
    "ConversationTurn",
    "ContextHints",
    "CONTEXT_MAX_HISTORY_TURNS",
    "CONTEXT_SUMMARY_FREQUENCY",
    "CONTEXT_SUMMARY_MIN_TURNS",
    "CONTEXT_TTL_SECONDS",
]
