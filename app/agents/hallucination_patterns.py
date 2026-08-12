"""Compatibility re-export for app.agents.validation.hallucination_patterns; implementation lives in the canonical package."""

from app.agents.validation.hallucination_patterns import (
    HallucinationPattern,
    detect_all_patterns,
    detect_date_hallucinations,
    detect_entity_hallucinations,
    detect_negation_hallucinations,
    detect_number_hallucinations,
)

__all__ = [
    "HallucinationPattern",
    "detect_date_hallucinations",
    "detect_number_hallucinations",
    "detect_entity_hallucinations",
    "detect_negation_hallucinations",
    "detect_all_patterns",
]
