"""
Quality Orchestrator Agent - Fuses quality scores from all validators.

Pure computation, no I/O, target <5ms execution time.
Combines route validation, retrieval quality, and answer validation into
comprehensive quality report with weighted scoring and penalty rules.
"""

import logging
from typing import Any

from app.agents.shared.config import (
    HALLUCINATION_HIGH_RISK_THRESHOLD,
    QUALITY_HIGH_THRESHOLD,
    QUALITY_LOW_THRESHOLD,
    QUALITY_MEDIUM_THRESHOLD,
    QUALITY_WEIGHT_ANSWER_FACT,
    QUALITY_WEIGHT_ANSWER_QUALITY,
    QUALITY_WEIGHT_CITATION,
    QUALITY_WEIGHT_RETRIEVAL,
    QUALITY_WEIGHT_ROUTE,
)
from app.agents.shared.quality_models import (
    AnswerValidationResult,
    ExecutionStats,
    QualityBreakdown,
    QualityReport,
    RetrievalQualityResult,
    RouteValidationResult,
)

logger = logging.getLogger(__name__)


def _classify_quality_level(confidence: float) -> tuple[str, str, str | None]:
    """
    Classify quality level based on confidence score.

    Args:
        confidence: Overall confidence score [0.0, 1.0]

    Returns:
        Tuple of (level, label, user_prompt)
        - level: "high" | "medium" | "low" | "very_low"
        - label: Chinese quality label
        - user_prompt: Warning message for user (None for high quality)
    """
    if confidence >= QUALITY_HIGH_THRESHOLD:
        return ("high", "高质量", None)
    elif confidence >= QUALITY_MEDIUM_THRESHOLD:
        return ("medium", "中等质量", "答案质量中等，建议结合其他来源验证")
    elif confidence >= QUALITY_LOW_THRESHOLD:
        return ("low", "低质量", "答案质量较低，请谨慎参考，建议人工核实")
    else:
        return ("very_low", "极低质量", "⚠️ 答案可能不准确，强烈建议人工审核")


def orchestrate_quality(
    route_validation: RouteValidationResult,
    retrieval_quality: RetrievalQualityResult,
    answer_validation: AnswerValidationResult,
    execution_metadata: dict[str, Any],
) -> QualityReport:
    """
    Fuse quality scores from all validators into comprehensive report.

    Pure computation, no I/O, target <5ms execution.

    Scoring weights:
    - Route confidence: 15%
    - Retrieval quality: 25%
    - Answer factuality: 40% (most important)
    - Answer quality: 15%
    - Citation completeness: 5%

    Penalty rules:
    - Hallucination risk > 0.3 → multiply by 0.7
    - Route confidence < 0.5 → multiply by 0.8

    Args:
        route_validation: Route validator result
        retrieval_quality: Retrieval quality result
        answer_validation: Answer validator result
        execution_metadata: Execution stats (total_time_ms, retry_count, etc)

    Returns:
        QualityReport with overall confidence and breakdown
    """
    # Extract scores for weighted fusion
    scores = {
        "route_confidence": route_validation.confidence,
        "retrieval_quality": retrieval_quality.overall_quality,
        "answer_factuality": answer_validation.validation_details.factual_consistency,
        "answer_quality": answer_validation.validation_details.answer_quality,
        "citation_completeness": answer_validation.validation_details.citation_completeness,
    }

    # Weighted average
    overall_confidence = (
        scores["route_confidence"] * QUALITY_WEIGHT_ROUTE
        + scores["retrieval_quality"] * QUALITY_WEIGHT_RETRIEVAL
        + scores["answer_factuality"] * QUALITY_WEIGHT_ANSWER_FACT
        + scores["answer_quality"] * QUALITY_WEIGHT_ANSWER_QUALITY
        + scores["citation_completeness"] * QUALITY_WEIGHT_CITATION
    )

    # Apply penalties
    if answer_validation.validation_details.hallucination_risk > HALLUCINATION_HIGH_RISK_THRESHOLD:
        overall_confidence *= 0.7
        logger.warning(f"High hallucination risk detected, confidence reduced to {overall_confidence:.3f}")

    if route_validation.confidence < 0.5:
        overall_confidence *= 0.8
        logger.warning(f"Low route confidence, overall confidence reduced to {overall_confidence:.3f}")

    # Clamp and round to 3 decimals
    overall_confidence = round(max(0.0, min(1.0, overall_confidence)), 3)

    # Classify quality level
    quality_level, quality_label, user_prompt = _classify_quality_level(overall_confidence)

    # Build breakdown
    breakdown = QualityBreakdown(
        route_decision={
            "score": route_validation.confidence,
            "status": "✓ 通过" if route_validation.is_valid else "⚠ 警告",
        },
        retrieval={
            "score": retrieval_quality.overall_quality,
            "status": "✓ 良好" if retrieval_quality.overall_quality >= 0.7 else "⚠ 一般",
        },
        answer_factuality={
            "score": answer_validation.validation_details.factual_consistency,
            "status": "✓ 可信" if answer_validation.validation_details.factual_consistency >= 0.8 else "⚠ 需核实",
        },
        citations={
            "score": answer_validation.validation_details.citation_completeness,
            "status": "✓ 完整" if answer_validation.validation_details.citation_completeness >= 0.8 else "⚠ 不完整",
        },
    )

    # Aggregate issues from all validators
    all_issues = []

    # Route warnings
    if route_validation.warnings:
        all_issues.extend([{"severity": "info", "component": "route", "message": w} for w in route_validation.warnings])

    # Retrieval issues
    if retrieval_quality.issues:
        all_issues.extend(
            [{"severity": "info", "component": "retrieval", "message": i} for i in retrieval_quality.issues]
        )

    # Answer issues
    if answer_validation.issues:
        all_issues.extend(
            [
                {
                    "severity": issue.severity,
                    "component": "answer",
                    "message": f"[{issue.type}] {issue.content[:50]}... - {issue.suggestion}",
                }
                for issue in answer_validation.issues
            ]
        )

    # Aggregate suggestions from retrieval
    all_suggestions = list(retrieval_quality.suggestions)

    # Calculate validation overhead
    validation_overhead = (
        route_validation.execution_time_ms + retrieval_quality.execution_time_ms + answer_validation.execution_time_ms
    )

    return QualityReport(
        overall_confidence=overall_confidence,
        quality_level=quality_level,
        quality_label=quality_label,
        user_prompt=user_prompt,
        breakdown=breakdown,
        issues=all_issues,
        suggestions=all_suggestions,
        execution_stats=ExecutionStats(
            total_time_ms=execution_metadata.get("total_time_ms", 0),
            validation_overhead_ms=validation_overhead,
            retry_count=execution_metadata.get("retry_count", 0),
            route_retry=execution_metadata.get("route_retry", 0),
            answer_retry=execution_metadata.get("answer_retry", 0),
        ),
    )
