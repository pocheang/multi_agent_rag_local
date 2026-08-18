"""Lazy compatibility adapters for legacy enhanced-query quality types."""

from __future__ import annotations

from typing import Any, Type


def get_quality_report_model() -> Type[Any]:
    """Return the legacy Pydantic quality-report model for response schemas."""
    from app.agents.shared.quality_models import QualityReport

    return QualityReport


def get_enhanced_quality_config_values() -> dict[str, Any]:
    """Load legacy quality settings exposed by the enhanced-query config endpoint."""
    from app.agents.shared.quality_config import (
        ANSWER_APPROVE_THRESHOLD,
        ANSWER_FLAG_THRESHOLD,
        QUALITY_HIGH_THRESHOLD,
        QUALITY_MEDIUM_THRESHOLD,
        RETRIEVAL_SAMPLE_TOP_K,
        ROUTE_HIGH_CONFIDENCE_THRESHOLD,
        ROUTE_MEDIUM_CONFIDENCE_THRESHOLD,
    )

    return {
        "answer_approve_threshold": ANSWER_APPROVE_THRESHOLD,
        "answer_flag_threshold": ANSWER_FLAG_THRESHOLD,
        "quality_high_threshold": QUALITY_HIGH_THRESHOLD,
        "quality_medium_threshold": QUALITY_MEDIUM_THRESHOLD,
        "retrieval_sample_top_k": RETRIEVAL_SAMPLE_TOP_K,
        "route_high_confidence_threshold": ROUTE_HIGH_CONFIDENCE_THRESHOLD,
        "route_medium_confidence_threshold": ROUTE_MEDIUM_CONFIDENCE_THRESHOLD,
    }
