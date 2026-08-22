"""Adapt the calibrated legacy router to the immutable domain contract."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable

from app.domain.contracts import RouteDecision
from app.orchestration.request import OrchestrationRequest

LegacyRouteDecider = Callable[..., object]

# Explicit connector/integration commands pattern
# Matches commands like: "disable connector X", "enable integration Y", "configure connector Z"
# Supports both uppercase and lowercase connector names, and various command verbs
_EXPLICIT_CONNECTOR_COMMAND = re.compile(
    r"^\s*(?:please\s+)?"  # Optional "please"
    r"(disable|enable|configure|remove|add|setup|connect|disconnect)\s+"  # Action verbs
    r"(?:the\s+)?"  # Optional "the"
    r"(connector|integration|plugin|extension)\s+"  # Target type
    r"([a-zA-Z][a-zA-Z0-9_\-]{0,63})"  # Connector name (now allows uppercase)
    r"\s*[.!]?\s*$",  # Optional punctuation
    re.IGNORECASE,
)


class RouterAgentService:
    """Expose one asynchronous, typed route decision boundary."""

    def __init__(self, decider: LegacyRouteDecider | None = None) -> None:
        self._decider = decider or self._default_decider

    async def route(self, request: OrchestrationRequest) -> RouteDecision:
        """Delegate routing once and normalize only the public orchestration fields."""
        # Check entire question text for connector commands, not just first line
        if _EXPLICIT_CONNECTOR_COMMAND.search(request.question):
            return RouteDecision(
                intent="tool_call",
                route="react",
                confidence=1.0,
                requires_plan=True,
                allowed_capabilities=frozenset({"rag", "tool"}),
                reason="explicit_owned_connector_command",
            )
        legacy = await asyncio.to_thread(
            self._decider,
            request.question,
            use_reasoning=request.use_reasoning,
            agent_class_hint=request.source_scope.agent_class_hint,
        )

        # Extract and validate fields from legacy router response
        try:
            # Access attributes directly - let AttributeError bubble up if missing
            route = str(legacy.route).lower() if legacy.route is not None else "vector"
            confidence = float(legacy.confidence) if legacy.confidence is not None else 0.5
            reason = str(legacy.reason) if legacy.reason is not None else "legacy_router"
        except (AttributeError, ValueError, TypeError) as exc:
            # Provide clear error message about what went wrong
            raise ValueError(
                f"Legacy router returned invalid response: {type(exc).__name__}: {exc}. "
                f"Expected object with 'route', 'confidence', and 'reason' attributes."
            ) from exc

        return _to_domain_route(route, confidence, reason)

    @staticmethod
    def _default_decider(*args: object, **kwargs: object) -> object:
        from app.agents.router.routing import decide_route

        return decide_route(*args, **kwargs)


def _to_domain_route(route: str, confidence: float, reason: str) -> RouteDecision:
    # Warn if confidence is out of valid range before normalization
    if confidence < 0.0 or confidence > 1.0:
        import logging

        logging.getLogger(__name__).warning(
            f"Router confidence out of range [0.0, 1.0]: {confidence:.4f} for route '{route}'. "
            f"Normalizing to valid range."
        )
    normalized_confidence = min(1.0, max(0.0, confidence))
    if route == "react":
        return RouteDecision(
            intent="tool_call",
            confidence=normalized_confidence,
            requires_plan=True,
            allowed_capabilities=frozenset({"rag", "tool"}),
            reason=reason,
        )
    if route == "hybrid":
        return RouteDecision(
            intent="hybrid",
            confidence=normalized_confidence,
            requires_plan=True,
            allowed_capabilities=frozenset({"rag"}),
            reason=reason,
        )
    if route == "web":
        return RouteDecision(
            intent="web_search",
            confidence=normalized_confidence,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag", "web"}),
            reason=reason,
        )
    if route not in {"vector", "graph"}:
        raise ValueError(
            f"router returned unsupported route: {route!r} (expected: vector, graph, react, hybrid, or web)"
        )
    return RouteDecision(
        intent="knowledge_retrieval",
        route=route,
        confidence=normalized_confidence,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason=reason,
    )
