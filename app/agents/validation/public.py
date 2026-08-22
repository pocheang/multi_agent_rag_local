"""Public answer-validation adapter backed by the canonical cascade."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.shared.config import (
    ANSWER_APPROVE_THRESHOLD,
    ANSWER_FLAG_THRESHOLD,
    ANSWER_WEIGHT_CITATION,
    ANSWER_WEIGHT_FACTUALITY,
    ANSWER_WEIGHT_QUALITY,
    ANSWER_WEIGHT_SAFETY,
    CASCADE_ENABLE_LEVEL1,
    CASCADE_ENABLE_LEVEL2,
    CASCADE_ENABLE_LEVEL3,
    CASCADE_ENABLE_LEVEL4,
    CASCADE_LEVEL1_TIMEOUT_MS,
    CASCADE_LEVEL2_TIMEOUT_MS,
    CASCADE_LEVEL3_TIMEOUT_MS,
    CASCADE_LEVEL4_TIMEOUT_MS,
    CASCADE_USE_FOR_VALIDATION,
    HALLUCINATION_HIGH_RISK_THRESHOLD,
)
from app.agents.shared.quality_models import (
    AnswerIssue,
    AnswerValidationDetails,
    AnswerValidationResult,
)
from app.agents.validation.cascade import ValidationCascade
from app.agents.validation.citations import citation_completeness as _validate_citations
from app.agents.validation.deep import deep_validation_score as _llm_deep_validation
from app.agents.validation.fact_verification import AnswerVerificationResult
from app.agents.validation.models import CascadeLevel, RuleBasisIssue, ValidationCascadeResult
from app.agents.validation.nli import (
    check_hallucination as _check_hallucination,
)
from app.agents.validation.nli import (
    extract_factual_spans as _extract_factual_spans,
)
from app.agents.validation.nli import (
    get_nli_model as _get_nli_model,
)
from app.agents.validation.rules import (
    assess_answer_quality as _assess_answer_quality,
)
from app.agents.validation.rules import (
    quick_validation as _quick_validation,
)
from app.agents.validation.rules import (
    safety_score as _safety_check,
)

logger = logging.getLogger(__name__)

_validation_cascade: ValidationCascade | None = None
_cascade_load_attempted = False


def _get_validation_cascade() -> ValidationCascade:
    """Build the process-wide cascade; the legacy engine no longer exists."""
    global _cascade_load_attempted, _validation_cascade
    if _validation_cascade is not None:
        return _validation_cascade
    _cascade_load_attempted = True
    if not CASCADE_USE_FOR_VALIDATION:
        logger.info("CASCADE_USE_FOR_VALIDATION is retired; using the single validation entry")
    _validation_cascade = ValidationCascade(
        config={
            "level1_timeout_ms": CASCADE_LEVEL1_TIMEOUT_MS,
            "level2_timeout_ms": CASCADE_LEVEL2_TIMEOUT_MS,
            "level3_timeout_ms": CASCADE_LEVEL3_TIMEOUT_MS,
            "level4_timeout_ms": CASCADE_LEVEL4_TIMEOUT_MS,
            "enable_level1": CASCADE_ENABLE_LEVEL1,
            "enable_level2": CASCADE_ENABLE_LEVEL2,
            "enable_level3": CASCADE_ENABLE_LEVEL3,
            "enable_level4": CASCADE_ENABLE_LEVEL4,
            "enforce_minimum_length": True,
        }
    )
    return _validation_cascade


async def validate_answer(
    query: str,
    answer: str,
    source_docs: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> AnswerValidationResult:
    """Validate an answer through :meth:`ValidationCascade.validate` only."""
    cascade_result = await _get_validation_cascade().validate(
        query,
        answer,
        source_docs,
        citations,
    )
    return _to_public_result(cascade_result)


async def verify_generated_answer(
    answer: str,
    source_docs: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]] | None = None,
) -> AnswerVerificationResult:
    """Run synthesis fact verification through the single cascade owner.

    This is a narrow result-shape adapter, not a second validation engine.
    ``ValidationCascade`` owns the actual fact-verification stage and its
    thresholds/fallback behavior.
    """
    return await _get_validation_cascade().run_fact_verification_stage(
        answer,
        source_docs,
        citations,
    )


def _to_public_result(cascade: ValidationCascadeResult) -> AnswerValidationResult:
    factuality = cascade.confidence_score
    hallucination_risk = 1.0 - factuality
    overall_score = (
        factuality * ANSWER_WEIGHT_FACTUALITY
        + cascade.citation_completeness * ANSWER_WEIGHT_CITATION
        + cascade.answer_quality * ANSWER_WEIGHT_QUALITY
        + cascade.safety_score * ANSWER_WEIGHT_SAFETY
    )
    if hallucination_risk > HALLUCINATION_HIGH_RISK_THRESHOLD:
        overall_score *= 0.7

    critical = any(issue.severity == "critical" for issue in cascade.all_issues)
    if critical:
        overall_score = 0.0
        action = "regenerate"
    elif overall_score >= ANSWER_APPROVE_THRESHOLD:
        action = "approve"
    elif overall_score >= ANSWER_FLAG_THRESHOLD:
        action = "flag"
    else:
        action = "regenerate"

    issues = [_to_answer_issue(issue) for issue in cascade.all_issues]
    if cascade.citation_completeness < 0.5 and not any(issue.type == "missing_citation" for issue in issues):
        issues.append(
            AnswerIssue(
                type="missing_citation",
                content="Incomplete citations",
                severity="medium",
                suggestion="Add citations for key claims",
            )
        )

    return AnswerValidationResult(
        is_valid=action != "regenerate",
        overall_score=round(max(0.0, min(1.0, overall_score)), 3),
        validation_details=AnswerValidationDetails(
            factual_consistency=round(factuality, 3),
            hallucination_risk=round(hallucination_risk, 3),
            citation_completeness=round(cascade.citation_completeness, 3),
            answer_quality=round(cascade.answer_quality, 3),
            safety_score=round(cascade.safety_score, 3),
        ),
        issues=issues,
        action=action,
        execution_time_ms=cascade.execution_time_ms,
        validation_method=_validation_method(cascade),
    )


def _to_answer_issue(issue: RuleBasisIssue) -> AnswerIssue:
    issue_type = issue.issue_type.lower()
    if issue_type.startswith("pii_") or "safety" in issue_type:
        public_type = "safety"
    elif "citation" in issue_type:
        public_type = "missing_citation"
    elif any(token in issue_type for token in ("hallucination", "contradiction", "mismatch")):
        public_type = "hallucination"
    else:
        public_type = "quality"
    severity = issue.severity if issue.severity in {"low", "medium", "high", "critical"} else "medium"
    return AnswerIssue(
        type=public_type,
        content=issue.content,
        severity=severity,
        suggestion=issue.suggestion or "",
    )


def _validation_method(cascade: ValidationCascadeResult) -> str:
    levels = {result.level for result in cascade.level_results}
    if CascadeLevel.DEEP_LLM in levels:
        return "deep"
    if CascadeLevel.NLI_BATCH in levels:
        return "standard"
    return "fast_path"


__all__ = [
    "_assess_answer_quality",
    "_check_hallucination",
    "_extract_factual_spans",
    "_get_nli_model",
    "_get_validation_cascade",
    "_llm_deep_validation",
    "_quick_validation",
    "_safety_check",
    "_validate_citations",
    "validate_answer",
    "verify_generated_answer",
]
