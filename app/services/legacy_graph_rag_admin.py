"""Lazy adapters for legacy Graph RAG administration."""

from __future__ import annotations

from typing import Any


def get_graph_rag_cache_stats() -> dict[str, Any]:
    """Delegate Graph RAG cache statistics to the legacy cache module."""
    from app.agents.graph_rag_cache import get_cache_stats

    return get_cache_stats()


def clear_graph_rag_caches() -> None:
    """Delegate clearing all legacy Graph RAG caches."""
    from app.agents.graph_rag_cache import clear_all_caches

    clear_all_caches()


def get_graph_rag_config_values() -> dict[str, Any]:
    """Load legacy Graph RAG settings needed by the administration response."""
    from app.agents.graph_rag_config import (
        DENSITY_ACCEPTABLE_MAX,
        DENSITY_ACCEPTABLE_MIN,
        DENSITY_OPTIMAL_MAX,
        DENSITY_OPTIMAL_MIN,
        GRAPH_PARAMS_HIGH_QUALITY,
        GRAPH_PARAMS_LOW_QUALITY,
        GRAPH_PARAMS_MEDIUM_QUALITY,
        MIN_ENTITIES_FOR_HIGH_CONFIDENCE,
        MIN_ENTITIES_FOR_MEDIUM_CONFIDENCE,
        QUALITY_THRESHOLD_HIGH,
        QUALITY_THRESHOLD_LOW,
        QUALITY_THRESHOLD_MEDIUM,
    )

    return {
        "density_acceptable_max": DENSITY_ACCEPTABLE_MAX,
        "density_acceptable_min": DENSITY_ACCEPTABLE_MIN,
        "density_optimal_max": DENSITY_OPTIMAL_MAX,
        "density_optimal_min": DENSITY_OPTIMAL_MIN,
        "graph_params_high_quality": GRAPH_PARAMS_HIGH_QUALITY,
        "graph_params_low_quality": GRAPH_PARAMS_LOW_QUALITY,
        "graph_params_medium_quality": GRAPH_PARAMS_MEDIUM_QUALITY,
        "min_entities_for_high_confidence": MIN_ENTITIES_FOR_HIGH_CONFIDENCE,
        "min_entities_for_medium_confidence": MIN_ENTITIES_FOR_MEDIUM_CONFIDENCE,
        "quality_threshold_high": QUALITY_THRESHOLD_HIGH,
        "quality_threshold_low": QUALITY_THRESHOLD_LOW,
        "quality_threshold_medium": QUALITY_THRESHOLD_MEDIUM,
    }
