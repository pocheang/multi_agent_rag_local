"""
Admin API routes for agent quality monitoring and analytics.

Provides comprehensive agent performance metrics including:
- Execution statistics
- Success/failure rates
- Performance trends
- Error distribution
- Real-time monitoring data
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.utils.auth_dependencies import require_admin
from app.services.agent_execution_tracker import AgentExecutionTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/agent-quality", tags=["admin-agent-quality"])


@router.get("/stats")
async def get_agent_quality_stats(
    _admin=require_admin,
) -> dict[str, Any]:
    """
    Get comprehensive agent quality statistics for dashboard.

    Returns aggregated metrics including:
    - Summary: total agents, executions, success rate, avg response time
    - Agent details: per-agent execution stats, success rates, timings
    - Timeline: success/failure counts over time
    - Error distribution: categorized error types and frequencies

    **Response Schema:**
    ```json
    {
        "summary": {
            "total_agents": 11,
            "total_executions": 1234,
            "overall_success_rate": 0.95,
            "avg_response_time": 2.34,
            "active_agents": 8
        },
        "agents": [
            {
                "agent_name": "EnhancedRouterAgent",
                "total_executions": 234,
                "success_count": 230,
                "failure_count": 4,
                "success_rate": 0.983,
                "avg_execution_time": 0.45,
                "avg_token_usage": 1234.5,
                "last_execution": "2026-07-02T10:30:00+00:00",
                "error_types": {"TimeoutError": 3, "ValueError": 1}
            }
        ],
        "timeline": [
            {
                "timestamp": "2026-07-02T10:00:00",
                "success": 45,
                "failure": 2
            }
        ],
        "error_distribution": {
            "TimeoutError": 12,
            "ValueError": 5,
            "ConnectionError": 3
        }
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        stats = tracker.get_quality_stats()

        logger.info(
            f"Retrieved agent quality stats: {stats['summary']['total_agents']} agents, "
            f"{stats['summary']['total_executions']} executions"
        )

        return stats

    except Exception as e:
        logger.exception("Failed to retrieve agent quality statistics")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve agent quality statistics: {str(e)}"
        )


@router.get("/agents/{agent_name}")
async def get_agent_details(
    agent_name: str,
    _admin=require_admin,
) -> dict[str, Any]:
    """
    Get detailed statistics for a specific agent.

    **Parameters:**
    - `agent_name`: Name of the agent (e.g., "EnhancedRouterAgent")

    **Response:**
    ```json
    {
        "agent_name": "EnhancedRouterAgent",
        "total_executions": 234,
        "success_count": 230,
        "failure_count": 4,
        "success_rate": 0.983,
        "avg_execution_time": 0.45,
        "avg_token_usage": 1234.5,
        "last_execution": "2026-07-02T10:30:00+00:00",
        "error_types": {"TimeoutError": 3, "ValueError": 1},
        "recent_executions": [...]
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        stats = tracker.get_quality_stats()

        # Find the specific agent
        agent_data = next((agent for agent in stats["agents"] if agent["agent_name"] == agent_name), None)

        if not agent_data:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found or has no execution data")

        return agent_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve details for agent '{agent_name}'")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve agent details: {str(e)}")


@router.get("/timeline")
async def get_execution_timeline(
    hours: int = Query(default=24, ge=1, le=168, description="Number of hours to include"),
    _admin=require_admin,
) -> dict[str, Any]:
    """
    Get execution timeline data for the specified time range.

    **Parameters:**
    - `hours`: Number of hours to include (1-168, default: 24)

    **Response:**
    ```json
    {
        "timeline": [
            {
                "timestamp": "2026-07-02T10:00:00",
                "success": 45,
                "failure": 2
            }
        ],
        "summary": {
            "total_success": 1180,
            "total_failure": 54,
            "success_rate": 0.956
        }
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        stats = tracker.get_quality_stats()

        timeline = stats["timeline"]
        total_success = sum(point["success"] for point in timeline)
        total_failure = sum(point["failure"] for point in timeline)
        total = total_success + total_failure

        return {
            "timeline": timeline,
            "summary": {
                "total_success": total_success,
                "total_failure": total_failure,
                "success_rate": total_success / total if total > 0 else 1.0,
            },
        }

    except Exception as e:
        logger.exception("Failed to retrieve execution timeline")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve execution timeline: {str(e)}")


@router.get("/errors")
async def get_error_distribution(
    _admin=require_admin,
) -> dict[str, Any]:
    """
    Get error distribution statistics.

    **Response:**
    ```json
    {
        "error_distribution": {
            "TimeoutError": 12,
            "ValueError": 5,
            "ConnectionError": 3
        },
        "total_errors": 20,
        "top_errors": [
            {"type": "TimeoutError", "count": 12, "percentage": 60.0}
        ]
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        stats = tracker.get_quality_stats()

        error_distribution = stats["error_distribution"]
        total_errors = sum(error_distribution.values())

        # Calculate top errors with percentages
        top_errors = [
            {"type": error_type, "count": count, "percentage": (count / total_errors * 100) if total_errors > 0 else 0}
            for error_type, count in sorted(error_distribution.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "error_distribution": error_distribution,
            "total_errors": total_errors,
            "top_errors": top_errors[:10],  # Top 10 errors
        }

    except Exception as e:
        logger.exception("Failed to retrieve error distribution")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve error distribution: {str(e)}")


@router.post("/clear")
async def clear_agent_stats(
    _admin=require_admin,
) -> dict[str, str]:
    """
    Clear all agent execution statistics.

    **Use with caution**: This will remove all historical execution data.

    **Response:**
    ```json
    {
        "status": "success",
        "message": "All agent execution statistics have been cleared"
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        tracker.clear_all_traces()

        logger.warning("Admin cleared all agent execution statistics")

        return {"status": "success", "message": "All agent execution statistics have been cleared"}

    except Exception as e:
        logger.exception("Failed to clear agent statistics")
        raise HTTPException(status_code=500, detail=f"Failed to clear agent statistics: {str(e)}")
