"""Admin language statistics routes."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import _require_permission, _require_user
from app.services.language.analytics import LanguageAnalytics

router = APIRouter(prefix="/admin/language", tags=["admin", "language"])


@router.get("/stats")
async def get_language_statistics(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Get system-wide language usage statistics.

    Requires admin:audit_read permission.

    Returns:
        dict with language usage statistics including:
            - total_queries: Total number of queries logged
            - language_distribution: Count by language
            - forced_vs_auto: Count of forced vs auto-detected
            - session_count: Number of unique sessions
            - recent_events: Last 100 events
    """
    _require_permission(user, "admin:audit_read", request, "admin")

    analytics = LanguageAnalytics.get_instance()
    return analytics.get_statistics()


@router.get("/stats/session/{session_id}")
async def get_session_language_statistics(
    session_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Get language usage statistics for a specific session.

    Requires admin:audit_read permission.

    Args:
        session_id: Session identifier

    Returns:
        dict with session-specific language statistics
    """
    _require_permission(user, "admin:audit_read", request, "admin")

    analytics = LanguageAnalytics.get_instance()
    return analytics.get_session_statistics(session_id)


@router.delete("/stats")
async def clear_language_statistics(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Clear all language usage statistics.

    Requires admin:ops_manage permission.

    Returns:
        dict with success message
    """
    _require_permission(user, "admin:ops_manage", request, "admin")

    analytics = LanguageAnalytics.get_instance()
    analytics.clear_statistics()

    return {"status": "success", "message": "Language statistics cleared"}
