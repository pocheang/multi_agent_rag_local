"""
API integration for query optimization service.

Adds optimization suggestions to query responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.query_optimization import QueryOptimizationService

if TYPE_CHECKING:
    from app.services.query_optimization import OptimizationSuggestion, QueryQuality


# ============================================================================
# Global Service Instance
# ============================================================================

_service: QueryOptimizationService | None = None


def get_optimization_service() -> QueryOptimizationService:
    """Get or create the global optimization service instance."""
    global _service
    if _service is None:
        _service = QueryOptimizationService()
    return _service


# ============================================================================
# API Response Enhancement
# ============================================================================


def should_suggest_optimization(quality: QueryQuality) -> bool:
    """
    Determine if optimization suggestions should be shown.

    Args:
        quality: Query quality assessment

    Returns:
        True if suggestions should be shown
    """
    # Show suggestions for medium, low, and very_low quality queries
    return quality.level in ("medium", "low", "very_low")


def format_suggestion_for_response(
    quality: QueryQuality,
    suggestion: OptimizationSuggestion,
) -> dict[str, object]:
    """
    Format suggestion for API response.

    Args:
        quality: Query quality assessment
        suggestion: Optimization suggestion

    Returns:
        Dictionary suitable for JSON response
    """
    return {
        "should_optimize": should_suggest_optimization(quality),
        "quality": {
            "score": quality.score,
            "level": quality.level,
            "issues": list(quality.issues),
        },
        "suggestion": {
            "message": suggestion.reasoning,
            "clarifications": list(suggestion.clarifications),
            "examples": list(suggestion.examples),
        },
    }


def analyze_query_for_api(query: str) -> dict[str, object]:
    """
    Analyze query and return API-ready response.

    Args:
        query: User query string

    Returns:
        Dictionary with quality and suggestions
    """
    service = get_optimization_service()
    quality, suggestion = service.analyze_and_suggest(query)
    return format_suggestion_for_response(quality, suggestion)
