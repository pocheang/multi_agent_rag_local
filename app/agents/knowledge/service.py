"""Knowledge Agent source-selection boundary with no retriever imports."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable

from app.core.config import Settings, get_settings
from app.domain.contracts import TaskPlan
from app.domain.knowledge import AccessScope, KnowledgeSource, KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import RouterDecision, VerificationDecision
from app.knowledge.width import MAX_SCALE, query_complexity, widen
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
        self._dynamic = active.dynamic_retrieval_enabled
        self._top_k_cap = active.dynamic_vector_top_k_cap
        self._rerank_top_n = active.reranker_top_n
        self._rerank_cap = active.dynamic_reranker_top_n_cap
        self._web_on_empty_corpus = active.web_search_on_empty_corpus

    async def decide(
        self,
        request: OrchestrationRequest,
        route: RouterDecision,
        plan: TaskPlan | None,
        retry_feedback: VerificationDecision | None = None,
        scope: AccessScope | None = None,
    ) -> KnowledgeStrategy:
        if self._decider is not None:
            try:
                strategy = await self._decider(request, route, plan, retry_feedback)
                return self._bounded(strategy, request, plan, scope)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return self._rule_strategy(
                    request,
                    route,
                    retry_feedback,
                    plan,
                    scope,
                    fallback_reason=f"structured_decider_fallback:{type(exc).__name__}",
                )
        return self._rule_strategy(request, route, retry_feedback, plan, scope)

    def _rule_strategy(
        self,
        request: OrchestrationRequest,
        route: RouterDecision,
        retry_feedback: VerificationDecision | None,
        plan: TaskPlan | None = None,
        scope: AccessScope | None = None,
        *,
        fallback_reason: str | None = None,
    ) -> KnowledgeStrategy:
        query = (retry_feedback.retry_query if retry_feedback else None) or request.question
        lowered = query.lower()
        hints = route.knowledge_hints
        selected: list[KnowledgeSource] = ["vector", "bm25"]
        reasons = ["local semantic and lexical evidence"]

        # The router's route is an instruction, not a suggestion: a `graph` or
        # `hybrid` route must reach the graph even when the wording carries none
        # of the relationship keywords below. Consulting only the keywords is
        # what silently degraded the graph route to vector+BM25.
        if "graph" in hints:
            selected.append("graph")
            reasons.append("graph route")
        elif _matches(lowered, r"关系|关联|依赖|上下游|路径|拓扑|relationship|dependency|connected|graph"):
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
        if "tool" in hints:
            selected.append("tool")
            reasons.append("router tool hint")
        # Two different authorizations, deliberately not the same one. The router
        # choosing the `web` route *is* permission to search the web. The
        # `use_web_fallback` request flag additionally allows a freshness-driven
        # web search on routes that did not ask for it. Requiring the flag for
        # both is what made `use_web_fallback=False` (the default on every chat
        # request) silently remove web search from the web route itself.
        wants_web = _matches(lowered, r"最新|实时|今天|当前价格|新闻|latest|current|today|news|price")
        if "web" in hints:
            selected.append("web")
            reasons.append("web route")
        elif request.use_web_fallback and wants_web:
            selected.append("web")
            reasons.append("authorized freshness fallback")
        elif self._web_on_empty_corpus and _has_no_documents(scope):
            # Third authorization, and the only one that does not depend on the
            # question. The other two ask whether this query would *benefit* from
            # the web; this one observes that local retrieval cannot answer at
            # all, because the caller has no documents for it to search. Without
            # it the only possible outcome is the "no evidence" message -- on
            # every question, for every account that has not uploaded anything,
            # which is the state every new account starts in.
            selected.append("web")
            reasons.append("empty document corpus")
        if retry_feedback is not None:
            reasons.append("verifier-directed retry")

        unique = tuple(dict.fromkeys(source for source in selected if source in self._available))
        if not unique:
            unique = tuple(source for source in ("vector", "bm25") if source in self._available)
        if not unique:
            raise RuntimeError("Knowledge Agent has no available source")
        ceiling = self._source_ceiling(plan)
        if len(unique) > ceiling:
            reasons.append(f"plan retrieval budget {ceiling}")
        unique = _keep_within(unique, ceiling, hints)
        top_k, rerank_top_n = self._widths(query)
        return KnowledgeStrategy(
            sources=tuple(self._source_plan(source, query, top_k) for source in unique),
            rewrite=True,
            rerank=len(unique) > 1,
            rerank_top_n=rerank_top_n,
            visual_required="multimodal" in unique,
            rationale="; ".join(([fallback_reason] if fallback_reason else []) + reasons),
        )

    def _source_ceiling(self, plan: TaskPlan | None) -> int:
        """How many sources this run may search.

        `TaskBudget.max_retrievals` is a count of *retrieval calls*, not a result
        width -- the planner derives it as 2 (vector+BM25) +1 for hybrid +1 for
        web, which is exactly the source list the rules above build. It was
        summed, checked against `PLANNER_MAX_RETRIEVAL_BUDGET`, and then dropped:
        no retriever ever read it, so a plan asking for two retrievals still got
        six sources.

        A total of zero means the plan holds no retrieval task at all (a pure
        tool-call plan). That is not an instruction to retrieve less -- the route
        is what decided retrieval is allowed here -- so the service ceiling
        stands rather than inventing a narrowing the planner never expressed.
        """
        if plan is None:
            return self._max_sources
        budget = sum(max(0, task.budget.max_retrievals) for task in plan.tasks)
        if budget <= 0:
            return self._max_sources
        return max(1, min(self._max_sources, budget))

    def _widths(self, query: str) -> tuple[int, int]:
        """Size the search and the answer set together, from query complexity.

        `DYNAMIC_RETRIEVAL_ENABLED` and the `DYNAMIC_*_CAP` settings only ever
        reached `candidate_collection.py`, which the chat path does not use, so
        every source got a flat `TOP_K` however complex the question was.

        The base stays `TOP_K` rather than the hybrid path's `VECTOR_TOP_K`:
        borrowing that default would widen every simple query too, which is a
        different decision than making complex ones wider. Reranking grows with
        it, because widening the search while holding `RERANKER_TOP_N` fixed just
        feeds the reranker more candidates and discards the extra ones.
        """
        if not self._dynamic:
            return self._top_k, self._rerank_top_n
        scale = min(MAX_SCALE, query_complexity(query))
        return (
            widen(self._top_k, self._top_k_cap, scale, step=2),
            widen(self._rerank_top_n, self._rerank_cap, scale, step=1),
        )

    def _bounded(
        self,
        strategy: KnowledgeStrategy,
        request: OrchestrationRequest,
        plan: TaskPlan | None = None,
        scope: AccessScope | None = None,
    ) -> KnowledgeStrategy:
        # A decider's strategy is untrusted input, so this is a ceiling, not a
        # default: it clamps to the widened cap rather than to `TOP_K`, which
        # would undo the complexity scaling `_widths` just applied.
        ceiling = self._source_ceiling(plan)
        top_k_ceiling = max(self._top_k, self._top_k_cap) if self._dynamic else self._top_k
        allowed: list[KnowledgeSourcePlan] = []
        seen: set[KnowledgeSource] = set()
        for source in strategy.sources:
            if source.source not in self._available or source.source in seen:
                continue
            # A decider's web plan needs the same authorization the rules need.
            # The route hint is not one of the options here: `_bounded` has no
            # route -- a decider that wanted the web because the route asked for
            # it should be reached through `_rule_strategy`, which does.
            if source.source == "web" and not (
                request.use_web_fallback or (self._web_on_empty_corpus and _has_no_documents(scope))
            ):
                continue
            seen.add(source.source)
            allowed.append(
                source.model_copy(
                    update={
                        "top_k": min(source.top_k, top_k_ceiling),
                        "timeout_ms": min(source.timeout_ms, self._timeout_ms),
                    }
                )
            )
            if len(allowed) >= ceiling:
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
            return self._rule_strategy(request, route, None, plan, scope, fallback_reason="empty_strategy_fallback")
        return strategy.model_copy(
            update={
                "sources": tuple(allowed),
                "visual_required": any(item.source == "multimodal" for item in allowed),
            }
        )

    def _source_plan(self, source: KnowledgeSource, query: str, top_k: int) -> KnowledgeSourcePlan:
        return KnowledgeSourcePlan(
            source=source,
            queries=(query,),
            top_k=top_k,
            timeout_ms=self._timeout_ms,
            required=source in {"vector", "bm25"},
        )


def _keep_within(
    sources: tuple[KnowledgeSource, ...],
    ceiling: int,
    hints: frozenset[str],
) -> tuple[KnowledgeSource, ...]:
    """Drop the least-warranted sources first, then restore selection order.

    Truncating the list as built would drop by *discovery* order, and the
    keyword rules happen to append `web` last -- so a plan whose budget was
    raised by one specifically because the route needs the web would spend that
    slot on `multimodal` instead. The planner derives its budget as 2 (the
    required local pair) + 1 for a hybrid route + 1 for web, so the ceiling has
    to be spent in that same order for the number to mean anything.

    A route hint outranks a keyword match for the same reason the hint outranks
    it during selection: the router decided, the regex only guessed.
    """
    if len(sources) <= ceiling:
        return sources

    def priority(source: KnowledgeSource) -> int:
        if source in {"vector", "bm25"}:
            return 0
        if source in hints:
            return 1
        return 2

    ranked = sorted(range(len(sources)), key=lambda i: (priority(sources[i]), i))
    kept = set(ranked[:ceiling])
    return tuple(source for index, source in enumerate(sources) if index in kept)


def _has_no_documents(scope: AccessScope | None) -> bool:
    """True when local document retrieval has nothing to search.

    `None` is not "no documents": it means the caller did not tell us, and
    guessing "empty" there would reach the web on every request that happens to
    omit a scope. Only an explicitly empty scope counts.
    """
    return scope is not None and not (scope.document_ids or scope.allowed_sources)


def _matches(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


__all__ = ["KnowledgeAgentService", "StrategyDecider"]
