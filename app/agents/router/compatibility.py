"""Compatibility routing adapters owned by the router capability."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from typing import Any

from app.agents.router.routing import LegacyRouteDecision, decide_route
from app.services.query_decomposer import QueryDecomposer

logger = logging.getLogger(__name__)


class RoutingService:
    """Compatibility service delegating to the calibrated router."""

    def route(
        self,
        question: str,
        *,
        use_reasoning: bool = False,
        agent_class_hint: str | None = None,
        use_llm_intent: bool = True,
    ) -> LegacyRouteDecision:
        return decide_route(
            question,
            use_reasoning=use_reasoning,
            agent_class_hint=agent_class_hint,
            use_llm_intent=use_llm_intent,
        )

    def route_many(
        self,
        questions: Iterable[str],
        *,
        use_reasoning: bool = False,
        agent_class_hint: str | None = None,
    ) -> list[LegacyRouteDecision]:
        return [
            self.route(
                question,
                use_reasoning=use_reasoning,
                agent_class_hint=agent_class_hint,
            )
            for question in questions
        ]


class DecompositionRoutingAdapter:
    """Compatibility decomposition flow followed by the canonical router."""

    def __init__(
        self,
        llm_client: Any,
        *,
        enable_query_decomposition: bool | None = None,
        routing_service: RoutingService | None = None,
    ) -> None:
        if enable_query_decomposition is None:
            enable_query_decomposition = os.getenv("ENABLE_QUERY_DECOMPOSITION", "false").lower() == "true"

        self.enable_query_decomposition = bool(enable_query_decomposition)
        self.routing_service = routing_service or RoutingService()
        self.query_decomposer = QueryDecomposer(llm_client) if self.enable_query_decomposition else None

        if self.query_decomposer is not None:
            logger.info("Query decomposition enabled")

    async def route_with_decomposition(
        self,
        question: str,
        *,
        use_reasoning: bool = False,
        agent_class_hint: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "original_question": question,
            "decomposed_query": None,
            "route_decisions": [],
        }

        if self.query_decomposer is not None:
            try:
                decomposed = await self.query_decomposer.decompose(question)
                result["decomposed_query"] = decomposed
                if len(decomposed.sub_queries) > 1:
                    decisions = self.routing_service.route_many(
                        decomposed.sub_queries,
                        use_reasoning=use_reasoning,
                        agent_class_hint=agent_class_hint,
                    )
                    result["route_decisions"] = [
                        {"query": sub_query, "decision": decision}
                        for sub_query, decision in zip(decomposed.sub_queries, decisions, strict=True)
                    ]
                    return result
            except Exception as exc:
                logger.error("Error during query decomposition: %s", exc)

        result["route_decisions"].append(
            {
                "query": question,
                "decision": self.routing_service.route(
                    question,
                    use_reasoning=use_reasoning,
                    agent_class_hint=agent_class_hint,
                ),
            }
        )
        return result
