"""
Analytics API Routes

Provides endpoints for retrieval analytics, agent performance, and document popularity.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.api.dependencies import _require_permission, _require_user
from app.services.retrieval.logger import RetrievalLogger

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def get_analytics_overview(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Get high-level analytics overview - Admin only.

    Returns:
        AnalyticsOverview: Total statistics including query count, success rate,
                          performance metrics, and distribution by agent/route
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    logger = RetrievalLogger.get_instance()
    return logger.get_overview()


@router.get("/agents")
async def get_agent_stats(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Get agent performance analysis - Admin only.

    Returns:
        list[AgentStats]: Performance statistics for each agent class,
                         sorted by query count descending
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    logger = RetrievalLogger.get_instance()
    return logger.get_agent_stats()


@router.get("/documents")
async def get_document_stats(
    request: Request, user: dict[str, Any] = Depends(_require_user), limit: int = Query(default=20, ge=1, le=100)
):
    """
    Get document popularity ranking - Admin only.

    Args:
        limit: Maximum number of documents to return (1-100, default: 20)

    Returns:
        list[DocumentStats]: Document usage statistics sorted by retrieval count
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    logger = RetrievalLogger.get_instance()
    return logger.get_document_stats(limit=limit)


@router.get("/export")
async def export_logs(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
    format: str = Query(default="json", pattern="^(json|csv)$"),
):
    """
    Export retrieval logs - Admin only.

    Args:
        format: Export format - "json" or "csv" (default: json)

    Returns:
        Response: Exported data with appropriate Content-Type headers
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    logger = RetrievalLogger.get_instance()
    data = logger.export_logs(format=format)

    if format == "csv":
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=retrieval_logs.csv"},
        )
    else:
        return Response(content=data, media_type="application/json")
