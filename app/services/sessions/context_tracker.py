"""Service-owned in-memory context tracking and cleanup lifecycle."""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.agents.shared.quality_models import ContextHints, ConversationContext, ConversationTurn
from app.core.shared_config import (
    CONTEXT_MAX_HISTORY_TURNS,
    CONTEXT_SUMMARY_FREQUENCY,
    CONTEXT_SUMMARY_MIN_TURNS,
    CONTEXT_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextKey:
    """The only context-store key; session IDs are never tenant-global."""

    user_id: str
    session_id: str


# Production would use Redis with proper serialization.
_context_store: dict[ContextKey, ConversationContext] = {}
_cleanup_task: asyncio.Task | None = None


async def _background_cleanup_loop():
    """Periodically remove expired contexts in long-running services."""
    logger.info("Context Tracker background cleanup task started")
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes
            cleaned = cleanup_expired_contexts()
            if cleaned > 0:
                logger.info(f"Background cleanup removed {cleaned} expired contexts")
                stats = get_store_stats()
                logger.debug(
                    f"Context store stats: {stats['active_sessions']} sessions, "
                    f"{stats['total_turns']} turns, {stats['total_entities']} entities"
                )
        except asyncio.CancelledError:
            logger.info("Context Tracker background cleanup task stopped")
            break
        except Exception as exc:
            logger.error("Background cleanup error: %s", exc, exc_info=True)
            await asyncio.sleep(60)  # Wait 1 minute before retry


def start_background_cleanup():
    """Start the cleanup task once during application startup."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(_background_cleanup_loop())
        logger.info("Started Context Tracker background cleanup")
    else:
        logger.warning("Background cleanup task already running")


def stop_background_cleanup():
    """Stop the cleanup task during application shutdown."""
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        logger.info("Stopped Context Tracker background cleanup")
    _cleanup_task = None


async def update_conversation_context(
    session_id: str,
    user_id: str,
    query: str,
    response: str,
    route: str,
    entities: list[str],
) -> None:
    """Update a session context with a completed conversation turn."""
    now = datetime.utcnow()
    key = ContextKey(user_id=str(user_id), session_id=str(session_id))
    if hash(key) % 10 == 0:
        cleanup_expired_contexts()

    if key not in _context_store:
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            conversation_history=[],
            topic_stack=[],
            entity_mentions={},
            current_intent=None,
            context_summary=None,
            last_update_time=now,
        )
        _context_store[key] = context
    else:
        context = _context_store[key]

    turn = ConversationTurn(
        query=query,
        response=response,
        route=route,
        entities=entities,
        timestamp=now,
    )
    context.conversation_history.append(turn)
    if len(context.conversation_history) > CONTEXT_MAX_HISTORY_TURNS:
        context.conversation_history = context.conversation_history[-CONTEXT_MAX_HISTORY_TURNS:]

    for entity in entities:
        context.entity_mentions[entity] = context.entity_mentions.get(entity, 0) + 1

    if not context.topic_stack or context.topic_stack[-1] != route:
        context.topic_stack.append(route)
        if len(context.topic_stack) > 5:
            context.topic_stack = context.topic_stack[-5:]

    context.current_intent = _detect_intent(query)
    context.last_update_time = now
    if len(context.conversation_history) >= CONTEXT_SUMMARY_MIN_TURNS:
        if len(context.conversation_history) % CONTEXT_SUMMARY_FREQUENCY == 0:
            asyncio.create_task(_generate_context_summary(key))


def get_context_aware_routing_hints(session_id: str, query: str, user_id: str = "anonymous") -> ContextHints:
    """Get synchronous routing hints from the stored conversation context."""
    key = ContextKey(user_id=str(user_id), session_id=str(session_id))
    if key not in _context_store:
        return ContextHints(
            resolve_references=None,
            followup=False,
            previous_route=None,
            focus_entities=[],
        )

    context = _context_store[key]
    previous_route = context.conversation_history[-1].route if context.conversation_history else None
    return ContextHints(
        resolve_references=_detect_reference_pronouns(query, context),
        followup=_is_followup_query(query, context),
        previous_route=previous_route,
        focus_entities=_get_top_entities(context, top_k=3),
    )


def resolve_query_with_context(query: str, hints: ContextHints) -> str:
    """Resolve supported English and Chinese references with context hints."""
    if not hints.resolve_references:
        return query

    resolved = query
    sorted_refs = sorted(hints.resolve_references.items(), key=lambda item: item[1], reverse=True)
    for entity, _ in sorted_refs:
        if "它" in resolved:
            resolved = resolved.replace("它", entity, 1)
        elif "他" in resolved:
            resolved = resolved.replace("他", entity, 1)
        elif "她" in resolved:
            resolved = resolved.replace("她", entity, 1)
        elif "这个" in resolved:
            resolved = resolved.replace("这个", entity, 1)
        elif "那个" in resolved:
            resolved = resolved.replace("那个", entity, 1)
        elif re.search(r"\bit\b", resolved, flags=re.IGNORECASE):
            resolved = re.sub(r"\bit\b", entity, resolved, count=1, flags=re.IGNORECASE)
        elif re.search(r"\bthis\b", resolved, flags=re.IGNORECASE):
            resolved = re.sub(r"\bthis\b", entity, resolved, count=1, flags=re.IGNORECASE)
        elif re.search(r"\bthat\b", resolved, flags=re.IGNORECASE):
            resolved = re.sub(r"\bthat\b", entity, resolved, count=1, flags=re.IGNORECASE)
    return resolved


def cleanup_expired_contexts() -> int:
    """Remove contexts whose last update time exceeds the configured TTL."""
    expiry_threshold = datetime.utcnow() - timedelta(seconds=CONTEXT_TTL_SECONDS)
    expired_sessions = [key for key, context in _context_store.items() if context.last_update_time < expiry_threshold]
    for key in expired_sessions:
        del _context_store[key]
    if expired_sessions:
        logger.debug("Cleaned up %s expired contexts", len(expired_sessions))
    return len(expired_sessions)


def clear_context(session_id: str, user_id: str = "anonymous") -> bool:
    """Clear one session context and report whether it existed."""
    key = ContextKey(user_id=str(user_id), session_id=str(session_id))
    if key in _context_store:
        del _context_store[key]
        return True
    return False


def get_context(session_id: str, user_id: str = "anonymous") -> ConversationContext | None:
    """Return the context stored for a session, if any."""
    return _context_store.get(ContextKey(user_id=str(user_id), session_id=str(session_id)))


def _detect_intent(query: str) -> str | None:
    """Detect high-level user intent for conversation tracking."""
    query_text = str(query or "").strip()
    query_lower = query_text.lower()
    comparison_keywords = ["compare", "difference", "versus", "vs", "对比", "区别", "差异", "比较"]
    navigation_keywords = [
        "show",
        "find",
        "search",
        "list",
        "browse",
        "example",
        "examples",
        "document",
        "documents",
        "搜索",
        "查找",
        "查看",
        "列出",
        "示例",
        "资料",
    ]
    clarification_keywords = [
        "explain more",
        "more details",
        "details",
        "elaborate",
        "clarify",
        "tell me more",
        "详细",
        "解释",
        "补充",
        "更多",
    ]
    question_keywords = [
        "what",
        "why",
        "how",
        "when",
        "where",
        "which",
        "what is",
        "什么",
        "为什么",
        "如何",
        "怎么",
        "哪个",
        "是什么",
    ]
    if any(keyword in query_lower for keyword in comparison_keywords):
        return "comparison"
    if any(keyword in query_lower for keyword in navigation_keywords):
        return "navigation"
    if any(keyword in query_lower for keyword in clarification_keywords):
        return "clarification"
    if query_text.endswith(("?", "？")) or any(keyword in query_lower for keyword in question_keywords):
        return "question"
    return "general_query"


def _is_followup_query(query: str, context: ConversationContext) -> bool:
    """Check if a query is a follow-up to previous conversation."""
    if not context.conversation_history:
        return False
    query_text = str(query or "").strip()
    query_lower = query_text.lower()
    if len(query_text) < 30:
        return True
    followup_indicators = [
        "also",
        "more",
        "further",
        "additionally",
        "what about",
        "tell me more",
        "还有",
        "另外",
        "继续",
        "进一步",
        "更多",
        "详细",
    ]
    if any(indicator in query_lower for indicator in followup_indicators):
        return True
    if context.entity_mentions and _detect_reference_pronouns(query_text, context):
        return True
    return False


def _detect_reference_pronouns(query: str, context: ConversationContext) -> dict[str, int] | None:
    """Return entity references when a query has a supported pronoun."""
    query_text = str(query or "")
    query_lower = query_text.lower()
    chinese_pronouns = ["它", "他", "她", "这个", "那个"]
    english_pronoun_patterns = [r"\bit\b", r"\bthis\b", r"\bthat\b", r"\bthese\b", r"\bthose\b"]
    has_chinese_pronoun = any(pronoun in query_text for pronoun in chinese_pronouns)
    has_english_pronoun = any(
        re.search(pattern, query_lower, flags=re.IGNORECASE) for pattern in english_pronoun_patterns
    )
    if (has_chinese_pronoun or has_english_pronoun) and context.entity_mentions:
        return context.entity_mentions
    return None


def _get_top_entities(context: ConversationContext, top_k: int = 3) -> list[str]:
    """Get the top K most mentioned entities."""
    if not context.entity_mentions:
        return []
    sorted_entities = sorted(context.entity_mentions.items(), key=lambda item: item[1], reverse=True)
    return [entity for entity, _ in sorted_entities[:top_k]]


async def _generate_context_summary(key: ContextKey):
    """Generate a non-blocking summary of recent conversation topics."""
    try:
        context = _context_store.get(key)
        if not context or len(context.conversation_history) < CONTEXT_SUMMARY_MIN_TURNS:
            return
        recent_queries = [turn.query for turn in context.conversation_history[-5:]]
        context.context_summary = f"Recent topics: {', '.join(recent_queries)}"
    except Exception as exc:
        logger.warning("Context summary generation failed for %s: %s", key, exc)


def get_all_sessions() -> list[str]:
    """Get all active session IDs."""
    return [key.session_id for key in _context_store]


def get_store_stats() -> dict[str, int]:
    """Get storage statistics."""
    total_turns = sum(len(ctx.conversation_history) for ctx in _context_store.values())
    total_entities = sum(len(ctx.entity_mentions) for ctx in _context_store.values())
    return {
        "active_sessions": len(_context_store),
        "total_turns": total_turns,
        "total_entities": total_entities,
    }
