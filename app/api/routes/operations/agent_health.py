"""
API routes for agent health checks and diagnostics.

GET /api/v1/agents/health - Check all agents health
GET /api/v1/agents/{agent_name}/health - Check specific agent health
GET /api/v1/agents/status - Get agent execution statistics
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.observability.agent_execution_tracker import AgentExecutionTracker
from app.services.legacy_agent_health import (
    available_agent_health_checks,
    get_agent_config_values,
    validate_agent,
    validate_all_agents,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agent-health"])


@router.get("/health")
async def check_all_agents_health() -> dict[str, Any]:
    """
    Check health status of all agents.

    Returns comprehensive validation results for all agents including:
    - Router Agent
    - Vector RAG Agent
    - Graph RAG Agent
    - ReAct Agent
    - Synthesis Agent
    - Enhanced Router Agent
    - LangGraph Workflow

    **Response:**
    ```json
    {
        "overall_status": "healthy|partially_healthy|degraded|unhealthy",
        "summary": {
            "total": 7,
            "ok": 6,
            "fallback": 1,
            "error": 0
        },
        "details": {
            "router": {"status": "ok", ...},
            "vector_rag": {"status": "ok", ...},
            ...
        }
    }
    ```
    """
    try:
        results = validate_all_agents()
        return results
    except Exception as e:
        logger.exception("Failed to check agents health")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/{agent_name}/health")
async def check_agent_health(agent_name: str) -> dict[str, Any]:
    """
    Check health status of a specific agent.

    **Supported agents:**
    - `router` - Router Agent
    - `vector_rag` - Vector RAG Agent
    - `graph_rag` - Graph RAG Agent
    - `react` - ReAct Agent
    - `synthesis` - Synthesis Agent
    - `enhanced_router` - Enhanced Router Agent
    - `workflow` - LangGraph Workflow

    **Example:**
    ```
    GET /api/v1/agents/router/health
    ```
    """
    available_checks = available_agent_health_checks()
    if agent_name not in available_checks:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found. Available: {list(available_checks)}"
        )

    try:
        result = validate_agent(agent_name)
        return result
    except Exception as e:
        logger.exception(f"Failed to check {agent_name} health")
        raise HTTPException(status_code=500, detail=f"Health check failed for {agent_name}: {str(e)}")


@router.get("/status")
async def get_agent_execution_status() -> dict[str, Any]:
    """
    Get agent execution statistics (legacy endpoint).

    **Deprecated**: Use `/api/v1/admin/agent-quality/stats` for comprehensive statistics.

    Returns basic execution statistics for all agents including:
    - Total executions
    - Average duration
    - Failure rate

    **Response:**
    ```json
    {
        "status": "ok",
        "statistics": {
            "router": {
                "executions": 1234,
                "avg_duration_ms": 50.2,
                "failures": 5,
                "avg_tokens": 1000
            }
        }
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        stats = tracker.get_execution_stats()

        return {
            "status": "ok",
            "statistics": stats,
        }
    except Exception as e:
        logger.exception("Failed to get agent execution status")
        raise HTTPException(status_code=500, detail=f"Failed to get execution status: {str(e)}")


@router.get("/trace/{execution_id}")
async def get_execution_trace(execution_id: str) -> dict[str, Any]:
    """
    Get detailed execution trace for a specific query.

    Returns the complete execution trace including all agent steps,
    timings, inputs, outputs, and decision rationales.

    **Parameters:**
    - `execution_id`: Execution ID from query response

    **Response:**
    ```json
    {
        "execution_id": "exec_123",
        "query": "ä»€ä¹ˆæ˜¯Dockerï¼Ÿ",
        "status": "completed",
        "start_time": "2026-07-02T10:00:00+00:00",
        "end_time": "2026-07-02T10:00:02+00:00",
        "total_duration_ms": 2000,
        "steps": [
            {
                "step_id": "step_1",
                "agent_name": "EnhancedRouterAgent",
                "status": "completed",
                "duration_ms": 450,
                "input_data": {...},
                "output_data": {...},
                "decision_rationale": "..."
            }
        ]
    }
    ```
    """
    try:
        tracker = AgentExecutionTracker.get_instance()
        trace = tracker.get_execution_trace(execution_id)

        if not trace:
            raise HTTPException(status_code=404, detail=f"Execution trace not found for ID: {execution_id}")

        return trace.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get execution trace for {execution_id}")
        raise HTTPException(status_code=500, detail=f"Failed to get execution trace: {str(e)}")


@router.get("/config")
async def get_agent_config() -> dict[str, Any]:
    """
    Get current agent configuration.

    Returns configuration for all agents including:
    - Valid routes
    - Valid skills
    - Valid agent classes
    - Retrieval strategies
    - Performance settings

    **Response:**
    ```json
    {
        "routes": ["vector", "graph", "hybrid", "react", "web"],
        "skills": ["answer_with_citations", "compare_entities", ...],
        "agent_classes": ["general", "cybersecurity", "pdf_text", "ai_knowledge"],
        "retrieval_strategies": ["hybrid", "dense", "bm25", "rerank"],
        "settings": {
            "max_context_chunks": 10,
            "query_expansion_enabled": true,
            ...
        }
    }
    ```
    """
    try:
        from app.core.config import get_settings

        settings = get_settings()
        config_values = get_agent_config_values()

        return {
            "routes": config_values["valid_routes"],
            "skills": config_values["valid_skills"],
            "agent_classes": config_values["valid_agent_classes"],
            "retrieval_strategies": ["hybrid", "dense", "bm25", "rerank"],
            "configuration": {
                "chunk_preview_length": config_values["chunk_preview_length"],
                "dense_score_threshold": config_values["dense_score_threshold"],
                "max_context_chunks": settings.max_context_chunks,
                "query_expansion_enabled": getattr(settings, "query_expansion_enabled", True),
                "graph_rag_enhanced": getattr(settings, "graph_rag_enhanced", True),
                "consistency_guard_enabled": getattr(settings, "consistency_guard_enabled", True),
            },
        }
    except Exception as e:
        logger.exception("Failed to get agent config")
        raise HTTPException(status_code=500, detail=f"Failed to get agent config: {str(e)}")


