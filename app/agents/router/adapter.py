"""
Integration adapter: Provides backward-compatible interface to refactored router.

This module allows gradual migration from the legacy decide_route() to the
new RoutingPipeline without breaking existing code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agents.router.pipeline import RoutingPipeline
from app.agents.router.routing import LegacyRouteDecision

if TYPE_CHECKING:
    from app.agents.router.pipeline import FinalRoute

logger = logging.getLogger(__name__)


# Singleton pipeline instance
_pipeline: RoutingPipeline | None = None


def get_pipeline() -> RoutingPipeline:
    """Get or create singleton routing pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RoutingPipeline()
    return _pipeline


def decide_route_refactored(
    question: str,
    use_reasoning: bool = False,
    agent_class_hint: str | None = None,
    use_llm_intent: bool = True,
) -> LegacyRouteDecision:
    """
    Backward-compatible wrapper for refactored routing pipeline.

    Signature matches the legacy decide_route() function but uses the
    new component-based architecture internally.

    Args:
        question: User question
        use_reasoning: Whether to use reasoning model
        agent_class_hint: Force specific agent class
        use_llm_intent: Use LLM for intent classification

    Returns:
        LegacyRouteDecision: Compatible with legacy code
    """
    pipeline = get_pipeline()

    result: FinalRoute = pipeline.decide(
        question,
        use_reasoning=use_reasoning,
        use_llm_intent=use_llm_intent,
        agent_class_hint=agent_class_hint,
    )

    return LegacyRouteDecision(
        route=result.route,
        reason=result.reason,
        skill=result.skill,
        agent_class=result.agent_class,
        confidence=result.confidence,
    )


# Compatibility export
__all__ = [
    "decide_route_refactored",
    "get_pipeline",
]
