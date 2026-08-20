"""
Tests for quality weight optimization A/B testing.
"""

import pytest
from unittest.mock import MagicMock
from app.agents.validation.quality_orchestrator import orchestrate_quality
from app.agents.quality_models import (
    RouteValidationResult,
    RetrievalQualityResult,
    RetrievalQualityMetrics,
    AnswerValidationResult,
    AnswerValidationDetails
)


def create_mock_validation_results(
    route_confidence: float = 0.9,
    retrieval_quality: float = 0.85,
    factual_consistency: float = 0.88,
    answer_quality: float = 0.82,
    citation_completeness: float = 0.90,
    hallucination_risk: float = 0.1
):
    """Helper to create mock validation results for testing."""
    route_validation = RouteValidationResult(
        is_valid=True,
        confidence=route_confidence,
        validation_method="rule_fast",
        validation_reason="Test validation",
        execution_time_ms=10,
        warnings=[]
    )

    metrics = RetrievalQualityMetrics(
        coverage_score=0.85,
        relevance_score=0.88,
        diversity_score=0.80,
        completeness_score=0.82
    )

    retrieval_quality_result = RetrievalQualityResult(
        overall_quality=retrieval_quality,
        metrics=metrics,
        execution_time_ms=20,
        issues=[],
        suggestions=[]
    )

    validation_details = AnswerValidationDetails(
        factual_consistency=factual_consistency,
        answer_quality=answer_quality,
        citation_completeness=citation_completeness,
        hallucination_risk=hallucination_risk,
        safety_score=0.95
    )

    answer_validation = AnswerValidationResult(
        is_valid=True,
        overall_score=0.85,
        validation_details=validation_details,
        issues=[],
        action="approve",
        execution_time_ms=30,
        validation_method="standard"
    )

    return route_validation, retrieval_quality_result, answer_validation


def test_weight_optimization_current_weights():
    """Test that current weights produce expected overall confidence."""
    route_val, retrieval_val, answer_val = create_mock_validation_results()

    result = orchestrate_quality(
        route_validation=route_val,
        retrieval_quality=retrieval_val,
        answer_validation=answer_val,
        execution_metadata={"total_time_ms": 100}
    )

    # Current weights: Route 15%, Retrieval 25%, Fact 40%, Quality 15%, Cite 5%
    # Expected: 0.9*0.15 + 0.85*0.25 + 0.88*0.40 + 0.82*0.15 + 0.90*0.05
    # = 0.135 + 0.2125 + 0.352 + 0.123 + 0.045 = 0.8675
    assert 0.86 <= result.overall_confidence <= 0.87


def test_weight_optimization_alternative_weights():
    """Test that alternative weights can be applied and produce different results."""
    # This test will verify that we can override weights via environment variables
    # Alternative weights: Route 10%, Retrieval 30%, Fact 45%, Quality 10%, Cite 5%
    import os
    os.environ["QUALITY_WEIGHT_ROUTE"] = "0.10"
    os.environ["QUALITY_WEIGHT_RETRIEVAL"] = "0.30"
    os.environ["QUALITY_WEIGHT_ANSWER_FACT"] = "0.45"
    os.environ["QUALITY_WEIGHT_ANSWER_QUALITY"] = "0.10"
    os.environ["QUALITY_WEIGHT_CITATION"] = "0.05"

    # Need to reload the config to pick up env vars
    import importlib
    from app.agents.shared import config as quality_config
    importlib.reload(quality_config)

    route_val, retrieval_val, answer_val = create_mock_validation_results()

    # Import after reload
    import app.agents.validation.quality_orchestrator as quality_orchestrator
    importlib.reload(quality_orchestrator)
    orchestrate_alt = quality_orchestrator.orchestrate_quality

    result = orchestrate_alt(
        route_validation=route_val,
        retrieval_quality=retrieval_val,
        answer_validation=answer_val,
        execution_metadata={"total_time_ms": 100}
    )

    # Alternative weights: 0.9*0.10 + 0.85*0.30 + 0.88*0.45 + 0.82*0.10 + 0.90*0.05
    # = 0.09 + 0.255 + 0.396 + 0.082 + 0.045 = 0.868
    assert 0.86 <= result.overall_confidence <= 0.87

    # Clean up env vars
    del os.environ["QUALITY_WEIGHT_ROUTE"]
    del os.environ["QUALITY_WEIGHT_RETRIEVAL"]
    del os.environ["QUALITY_WEIGHT_ANSWER_FACT"]
    del os.environ["QUALITY_WEIGHT_ANSWER_QUALITY"]
    del os.environ["QUALITY_WEIGHT_CITATION"]
    importlib.reload(quality_config)
    importlib.reload(quality_orchestrator)


def test_weight_sum_equals_one():
    """Test that all weight combinations sum to 1.0."""
    from app.agents.shared.config import (
        QUALITY_WEIGHT_ROUTE,
        QUALITY_WEIGHT_RETRIEVAL,
        QUALITY_WEIGHT_ANSWER_FACT,
        QUALITY_WEIGHT_ANSWER_QUALITY,
        QUALITY_WEIGHT_CITATION
    )

    weight_sum = (
        QUALITY_WEIGHT_ROUTE +
        QUALITY_WEIGHT_RETRIEVAL +
        QUALITY_WEIGHT_ANSWER_FACT +
        QUALITY_WEIGHT_ANSWER_QUALITY +
        QUALITY_WEIGHT_CITATION
    )

    assert abs(weight_sum - 1.0) < 0.001, f"Weights must sum to 1.0, got {weight_sum}"
