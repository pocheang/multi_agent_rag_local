"""API endpoints for evaluation."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies import _require_permission, _require_user
from app.api.transport.errors import bad_request, internal_error, not_found
from app.evaluation import (
    EvaluationMetrics,
    EvaluationService,
    TestQuery,
    load_test_queries,
)
from app.evaluation.baselines.api_retriever import SUPPORTED_SYSTEMS, SimpleRetriever, create_api_retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


# Request/Response models
class RunEvaluationRequest(BaseModel):
    system: str  # "vector_only", "hybrid", "rerank"
    queries: list[str] | None = None  # Optional: specific query IDs
    query_file: str = "data/evaluation/demo_queries.json"


class RunEvaluationResponse(BaseModel):
    run_id: str
    system: str
    status: str
    metrics: EvaluationMetrics | None = None
    message: str


class CompareSystemsRequest(BaseModel):
    systems: list[str]  # List of system names to compare
    query_file: str = "data/evaluation/demo_queries.json"


class EvaluationMetricsResponse(BaseModel):
    precision_at_5: float
    recall_at_5: float
    f1_at_5: float
    mrr: float
    ndcg_at_5: float
    avg_latency_ms: float
    total_queries: int


class SystemComparisonResponse(BaseModel):
    system_name: str
    metrics: EvaluationMetricsResponse


def get_retriever(system_name: str):
    """Get retriever instance by system name.

    Args:
        system_name: "vector_only", "hybrid", or "rerank"

    Returns:
        SimpleRetriever instance configured for the system

    Raises:
        HTTPException: If system name is invalid
    """
    try:
        return create_api_retriever(system_name)
    except ValueError as exc:
        raise bad_request(str(exc))


@router.get("/queries", response_model=list[TestQuery])
async def list_queries(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
    query_file: str = "data/evaluation/demo_queries.json",
    category: str | None = None,
    difficulty: str | None = None,
):
    """
    List all test queries - Admin only.

    Args:
        query_file: Path to test query JSON file
        category: Optional category filter
        difficulty: Optional difficulty filter

    Returns:
        List of test queries
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    try:
        queries = load_test_queries(query_file)

        if category:
            queries = [q for q in queries if q.category == category]

        if difficulty:
            queries = [q for q in queries if q.difficulty == difficulty]

        return queries
    except FileNotFoundError as e:
        raise not_found(str(e))
    except Exception as e:
        logger.error(f"Error loading queries: {e}")
        raise internal_error(str(e))


@router.post("/run", response_model=RunEvaluationResponse)
async def run_evaluation(
    request_data: RunEvaluationRequest, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    """
    Run evaluation on a specified system - Admin only.

    Args:
        request_data: RunEvaluationRequest with system name and optional query IDs

    Returns:
        RunEvaluationResponse with metrics and run ID

    Note: This endpoint requires retriever implementation to be completed.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    try:
        # Load test queries
        all_queries = load_test_queries(request_data.query_file)

        # Filter queries if specific IDs provided
        if request_data.queries:
            queries = [q for q in all_queries if q.id in request_data.queries]
            if not queries:
                raise bad_request("No matching queries found")
        else:
            queries = all_queries

        # Get retriever (currently not implemented)
        retriever = get_retriever(request_data.system)

        # Run evaluation
        logger.info(f"Running evaluation for {request_data.system} on {len(queries)} queries")
        service = EvaluationService()
        eval_run = service.evaluate_system(retriever, queries, request_data.system)

        # Save results
        results_dir = Path("data/evaluation/results")
        results_dir.mkdir(parents=True, exist_ok=True)
        results_path = results_dir / f"{eval_run.run_id}.json"

        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(eval_run.model_dump(), f, indent=2)

        return RunEvaluationResponse(
            run_id=eval_run.run_id,
            system=request_data.system,
            status="completed",
            metrics=eval_run.metrics,
            message=f"Evaluation completed successfully on {len(queries)} queries",
        )

    except FileNotFoundError as e:
        raise not_found(str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running evaluation: {e}")
        raise internal_error(str(e))


@router.get("/results/{run_id}")
async def get_results(run_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Get evaluation results by run ID - Admin only.

    Args:
        run_id: Run ID from previous evaluation

    Returns:
        Evaluation results
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    results_path = Path(f"data/evaluation/results/{run_id}.json")

    if not results_path.exists():
        raise not_found(f"Results not found for run_id: {run_id}")

    with open(results_path, encoding="utf-8") as f:
        return json.load(f)


@router.post("/compare", response_model=list[SystemComparisonResponse])
async def compare_systems(
    request_data: CompareSystemsRequest, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    """
    Compare multiple systems - Admin only.

    Args:
        request_data: CompareSystemsRequest with list of system names

    Returns:
        List of SystemComparison with comparative metrics

    Note: This endpoint requires retriever implementation to be completed.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    try:
        # Load test queries
        queries = load_test_queries(request_data.query_file)

        # Get retrievers for each system
        retrievers = {}
        for system_name in request_data.systems:
            logger.info(f"Loading retriever for {system_name}...")
            retrievers[system_name] = get_retriever(system_name)

        # Run comparison
        service = EvaluationService()
        comparisons = service.compare_systems(retrievers, queries)

        # Convert to response format
        return [
            SystemComparisonResponse(
                system_name=comp.system_name, metrics=EvaluationMetricsResponse(**comp.metrics.model_dump())
            )
            for comp in comparisons
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing systems: {e}")
        raise internal_error(str(e))


@router.get("/systems")
async def list_systems(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    List available retrieval systems for evaluation - Admin only.

    Returns:
        Dictionary of available system names
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    return {
        "systems": list(SUPPORTED_SYSTEMS),
        "count": len(SUPPORTED_SYSTEMS),
        "note": "Evaluation baselines are provided by app.evaluation.baselines.api_retriever.",
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "evaluation", "timestamp": datetime.now().isoformat()}


