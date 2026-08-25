"""Knowledge Agent source-selection boundary with no retriever imports."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable

from app.core.config import Settings, get_settings
from app.domain.contracts import TaskPlan
from app.domain.knowledge import KnowledgeSource, KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import RouterDecision, VerificationDecision
from app.orchestration.request import OrchestrationRequest

StrategyDecider = Callable[
    [OrchestrationRequest, RouterDecision, TaskPlan | None, VerificationDecision | None],
    Awaitable[KnowledgeStrategy],
]

_ALL_SOURCES: frozenset[KnowledgeSource] = frozenset(
    {"vector", "bm25", "graph", "wiki", "memory", "multimodal", "web", "tool"}
)


class KnowledgeAgentService:
    """Choose a bounded retrieval strategy, never execute it."""

    def __init__(
        self,
        decider: StrategyDecider | None = None,
        *,
        available_sources: Iterable[KnowledgeSource] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._decider = decider
        self._available = frozenset(available_sources or _ALL_SOURCES)
        active = settings or get_settings()
        self._top_k = active.top_k
        self._timeout_ms = active.knowledge_source_timeout_ms
        self._max_sources = active.knowledge_max_sources

    async def decide(
        self,
        request: OrchestrationRequest,
        route: RouterDecision,
        plan: TaskPlan | None,
        retry_feedback: VerificationDecision | None = None,
    ) -> KnowledgeStrategy:
        if self._decider is not None:
            try:
                strategy = await self._decider(request, route, plan, retry_feedback)
                return self._bounded(strategy, request)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return self._rule_strategy(
                    request,
                    route,
                    retry_feedback,
                    fallback_reason=f"structured_decider_fallback:{type(exc).__name__}",
                )
        return self._rule_strategy(request, route, retry_feedback)

    def _rule_strategy(
        self,
        request: OrchestrationRequest,
        route: RouterDecision,
        retry_feedback: VerificationDecision | None,
        *,
        fallback_reason: str | None = None,
    ) -> KnowledgeStrategy:
        query = (retry_feedback.retry_query if retry_feedback else None) or request.question
        lowered = query.lower()
        selected: list[KnowledgeSource] = ["vector", "bm25"]
        reasons = ["local semantic and lexical evidence"]

        if _matches(lowered, r"关系|关联|依赖|上下游|路径|拓扑|relationship|dependency|connected|graph"):
            selected.append("graph")
            reasons.append("relationship query")
        if _matches(lowered, r"图片|图表|架构图|流程图|统计图|页面布局|image|diagram|chart|figure|visual"):
            selected.append("multimodal")
            reasons.append("visual evidence required")
        if _matches(lowered, r"我的偏好|我之前|上次|长期记忆|remember|my preference|last time"):
            selected.append("memory")
            reasons.append("governed long-term context")
        if _matches(lowered, r"wiki|知识条目|术语定义|百科"):
            selected.append("wiki")
            reasons.append("derived knowledge requested")
        if "tool" in route.knowledge_hints:
            selected.append("tool")
            reasons.append("router tool hint")
        wants_web = _matches(lowered, r"最新|实时|今天|当前价格|新闻|latest|current|today|news|price")
        if request.use_web_fallback and (wants_web or "web" in route.knowledge_hints):
            selected.append("web")
            reasons.append("authorized freshness fallback")
        if retry_feedback is not None:
            reasons.append("verifier-directed retry")

        unique = tuple(dict.fromkeys(source for source in selected if source in self._available))
        if not unique:
            unique = tuple(source for source in ("vector", "bm25") if source in self._available)
        if not unique:
            raise RuntimeError("Knowledge Agent has no available source")
        unique = unique[: self._max_sources]
        return KnowledgeStrategy(
            sources=tuple(self._source_plan(source, query) for source in unique),
            rewrite=True,
            rerank=len(unique) > 1,
            visual_required="multimodal" in unique,
            rationale="; ".join(([fallback_reason] if fallback_reason else []) + reasons),
        )

    def _bounded(self, strategy: KnowledgeStrategy, request: OrchestrationRequest) -> KnowledgeStrategy:
        allowed: list[KnowledgeSourcePlan] = []
        seen: set[KnowledgeSource] = set()
        for source in strategy.sources:
            if source.source not in self._available or source.source in seen:
                continue
            if source.source == "web" and not request.use_web_fallback:
                continue
            seen.add(source.source)
            allowed.append(
                source.model_copy(
                    update={
                        "top_k": min(source.top_k, self._top_k),
                        "timeout_ms": min(source.timeout_ms, self._timeout_ms),
                    }
                )
            )
            if len(allowed) >= self._max_sources:
                break
        if not allowed:
            route = RouterDecision(
                intent="knowledge_retrieval",
                complexity="simple",
                completeness="complete",
                next_stage="knowledge",
                confidence=0,
                reason="safe local fallback",
            )
            return self._rule_strategy(request, route, None, fallback_reason="empty_strategy_fallback")
        return strategy.model_copy(
            update={
                "sources": tuple(allowed),
                "visual_required": any(item.source == "multimodal" for item in allowed),
            }
        )

    def _source_plan(self, source: KnowledgeSource, query: str) -> KnowledgeSourcePlan:
        return KnowledgeSourcePlan(
            source=source,
            queries=(query,),
            top_k=self._top_k,
            timeout_ms=self._timeout_ms,
            required=source in {"vector", "bm25"},
        )


def _matches(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


__all__ = ["KnowledgeAgentService", "StrategyDecider"]
