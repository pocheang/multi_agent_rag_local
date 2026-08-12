"""Compatibility exports for the canonical routing implementation."""

from app.agents.router.routing import (
    ROUTER_PROMPT,
    RouteDecision,
    decide_route,
    decide_route_simple,
    get_calibration_stats,
    record_routing_feedback,
)

__all__ = [
    "RouteDecision",
    "ROUTER_PROMPT",
    "decide_route",
    "decide_route_simple",
    "record_routing_feedback",
    "get_calibration_stats",
]
