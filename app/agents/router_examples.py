"""Compatibility re-export for app.agents.router.examples; implementation lives in the canonical package."""

from app.agents.router.examples import (
    EXAMPLE_GRAPH_QUERIES,
    EXAMPLE_HYBRID_QUERIES,
    EXAMPLE_REACT_QUERIES,
    EXAMPLE_VECTOR_QUERIES,
    format_examples_for_prompt,
    get_few_shot_examples_by_route,
    get_mixed_examples,
)

__all__ = [
    "EXAMPLE_VECTOR_QUERIES",
    "EXAMPLE_GRAPH_QUERIES",
    "EXAMPLE_HYBRID_QUERIES",
    "EXAMPLE_REACT_QUERIES",
    "get_few_shot_examples_by_route",
    "format_examples_for_prompt",
    "get_mixed_examples",
]
