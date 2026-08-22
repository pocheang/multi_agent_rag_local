"""
Session-related helper functions for the QueryMind API.
"""

from typing import Any

from app.api.transport.errors import bad_request, not_found
from app.core.config import get_settings
from app.services.sessions.history import HistoryStore, validate_session_id

settings = get_settings()


def _history_store_for_user(user: dict[str, Any]) -> HistoryStore:
    """Get the history store for a user."""
    return HistoryStore(base_dir=settings.sessions_path / user["user_id"])


def _require_valid_session_id(session_id: str) -> str:
    """Validate and return a session ID."""
    try:
        return validate_session_id(session_id)
    except ValueError:
        raise bad_request("invalid session_id format")


def _require_existing_session_for_query(user: dict[str, Any], session_id: str | None) -> str | None:
    """
    确保查询有有效的session，如果不存在则自动创建。

    这提供了更好的用户体验：
    - 用户无需手动创建session
    - 刷新页面后不会丢失查询能力
    - 前端可以延迟session创建

    Args:
        user: 认证用户信息
        session_id: 可选的session ID

    Returns:
        str | None: 有效的session ID，或None（表示无session的查询）
    """
    if not session_id:
        return None

    normalized = _require_valid_session_id(session_id)
    history_store = _history_store_for_user(user)

    # 检查session是否存在
    if history_store.get_session(normalized) is None:
        # Session不存在，自动创建而非报错
        # 这大大改善了用户体验，特别是在：
        # 1. 用户刷新页面后session丢失
        # 2. 前端传递了新的session_id但还未显式创建
        # 3. 测试环境中快速原型开发
        try:
            created = history_store.create_session(session_id=normalized)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"Auto-created session {normalized[:8]}... for user {user.get('user_id', 'unknown')[:8]}..."
            )
            return created["session_id"]
        except Exception as e:
            # 创建失败时才报错
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to auto-create session: {e}")
            raise bad_request(f"Failed to create session: {str(e)}")

    return normalized


def _latest_answer_for_same_question(user: dict[str, Any], session_id: str | None, question: str) -> str | None:
    """Get the latest answer for the same question in a session."""
    if not session_id:
        return None
    session_data = _history_store_for_user(user).get_session(session_id) or {}
    msgs = list(session_data.get("messages", []) or [])
    if not msgs:
        return None
    target = str(question or "").strip()
    for i in range(len(msgs) - 2, -1, -1):
        m = msgs[i]
        if str(m.get("role", "")) != "user":
            continue
        if str(m.get("content", "")).strip() != target:
            continue
        for j in range(i + 1, len(msgs)):
            n = msgs[j]
            if str(n.get("role", "")) == "assistant":
                return str(n.get("content", "") or "")
        break
    return None
