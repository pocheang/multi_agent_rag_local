"""Deprecated compatibility wrapper for decomposition-aware routing."""

from __future__ import annotations

from typing import Any

from app.agents.router.routing import RouteDecision
from app.agents.router.compatibility import DecompositionRoutingAdapter, RoutingService


class EnhancedRouterAgent:
    """Compatibility wrapper; it owns no routing rules or second route path."""

    def __init__(
        self,
        llm_client: Any,
        enable_query_decomposition: bool | None = None,
        *,
        routing_service: RoutingService | None = None,
    ) -> None:
        """Initialize the legacy wrapper around the router compatibility adapter."""
        self._adapter = DecompositionRoutingAdapter(
            llm_client,
            enable_query_decomposition=enable_query_decomposition,
            routing_service=routing_service,
        )
        self.enable_query_decomposition = self._adapter.enable_query_decomposition
        self.query_decomposer = self._adapter.query_decomposer

    async def route_with_decomposition(
        self, question: str, use_reasoning: bool = False, agent_class_hint: str | None = None
    ) -> dict[str, Any]:
        """Route through the shared adapter, preserving the legacy result shape."""
        return await self._adapter.route_with_decomposition(
            question,
            use_reasoning=use_reasoning,
            agent_class_hint=agent_class_hint,
        )


def route_with_decomposition_sync(
    question: str, use_reasoning: bool = False, agent_class_hint: str | None = None
) -> RouteDecision:
    """Deprecated synchronous compatibility wrapper for route selection."""
    return RoutingService().route(
        question,
        use_reasoning=use_reasoning,
        agent_class_hint=agent_class_hint,
    )
