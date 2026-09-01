"""The plan's retrieval budget and the query's complexity have to reach retrieval.

Two independent things were computed and thrown away.

`TaskBudget.max_retrievals` is a count of retrieval *calls* -- the planner
derives it as 2 (the required local pair) + 1 for a hybrid route + 1 for web --
and `PlannerAgentService` summed it, checked it against
`PLANNER_MAX_RETRIEVAL_BUDGET`, and dropped it. No retriever read it, so a plan
asking for two retrievals still searched six sources.

`DYNAMIC_RETRIEVAL_ENABLED` and the `DYNAMIC_*_CAP` settings only ever reached
`candidate_collection.py`, which the chat path does not use: on the chat path
every source got a flat `TOP_K` however complex the question was.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.knowledge.service import KnowledgeAgentService
from app.core.config import Settings
from app.domain.contracts import PlannedTask, TaskBudget, TaskPlan
from app.domain.knowledge import KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import RouterDecision
from app.orchestration.request import OrchestrationRequest

SIMPLE = "什么是 RAG"
COMPLEX = "请对比 A 架构与 B 架构在多阶段检索上的 trade-off，分别有哪些成本？各自的延迟表现如何？"
MANY_SOURCES = "关系 图片 我的偏好 wiki 最新"


def _route(*hints: str) -> RouterDecision:
    return RouterDecision(
        intent="knowledge_retrieval",
        complexity="simple",
        completeness="complete",
        next_stage="knowledge",
        confidence=0.9,
        reason="test",
        knowledge_hints=frozenset(hints),
    )


def _plan(*budgets: int) -> TaskPlan:
    return TaskPlan(
        tasks=tuple(
            PlannedTask(
                task_id=f"t{index}",
                prompt="do the thing",
                budget=TaskBudget(max_retrievals=budget, max_tool_calls=0),
            )
            for index, budget in enumerate(budgets)
        )
    )


def _decide(question: str, *, route: RouterDecision | None = None, plan: TaskPlan | None = None) -> KnowledgeStrategy:
    service = KnowledgeAgentService()
    request = OrchestrationRequest(question=question, use_web_fallback=True)
    return asyncio.run(service.decide(request, route or _route("vector", "bm25", "graph", "web"), plan))


def _sources(strategy: KnowledgeStrategy) -> tuple[str, ...]:
    return tuple(plan.source for plan in strategy.sources)


class TestPlanBudget:
    def test_a_two_retrieval_plan_searches_two_sources(self) -> None:
        assert _sources(_decide(MANY_SOURCES, plan=_plan(2))) == ("vector", "bm25")

    def test_without_a_plan_the_service_ceiling_stands(self) -> None:
        assert len(_decide(MANY_SOURCES).sources) > 2

    def test_the_budget_is_spent_on_what_the_route_asked_for(self) -> None:
        """The planner's +1 is *for* web. Truncating in discovery order spent it
        on `multimodal`, because the keyword rules append web last."""
        assert _sources(_decide(MANY_SOURCES, plan=_plan(4))) == ("vector", "bm25", "graph", "web")

    def test_budgets_sum_across_tasks(self) -> None:
        """`PlannerAgentService` validates the sum, so the ceiling reads the sum."""
        assert len(_decide(MANY_SOURCES, plan=_plan(2, 1)).sources) == 3

    def test_a_plan_with_no_retrieval_task_does_not_narrow_retrieval(self) -> None:
        """A pure tool-call plan budgets zero retrievals. That is the absence of an
        instruction, not an instruction to search less -- the route already decided
        retrieval is allowed here."""
        assert len(_decide(MANY_SOURCES, plan=_plan(0)).sources) > 1

    def test_the_required_local_pair_survives_the_smallest_budget(self) -> None:
        assert _sources(_decide(MANY_SOURCES, plan=_plan(1)))[0] == "vector"


class TestQueryComplexity:
    def test_a_simple_query_keeps_the_configured_width(self) -> None:
        """Scaling must be additive on top of `TOP_K`, not a new default: a change
        here widens every query in the system."""
        settings = Settings()
        strategy = _decide(SIMPLE)

        assert strategy.sources[0].top_k == settings.top_k
        assert strategy.rerank_top_n == settings.reranker_top_n

    def test_a_complex_query_searches_wider(self) -> None:
        simple = _decide(SIMPLE)
        complex_ = _decide(COMPLEX)

        assert complex_.sources[0].top_k > simple.sources[0].top_k

    def test_reranking_widens_with_the_search(self) -> None:
        """Widening `top_k` alone just feeds the reranker more candidates and
        throws the extra ones away."""
        assert _decide(COMPLEX).rerank_top_n > _decide(SIMPLE).rerank_top_n

    def test_widths_stay_under_their_caps(self) -> None:
        settings = Settings()
        strategy = _decide(COMPLEX * 4)

        assert strategy.sources[0].top_k <= settings.dynamic_vector_top_k_cap
        assert strategy.rerank_top_n <= settings.dynamic_reranker_top_n_cap

    def test_the_switch_turns_it_off(self) -> None:
        service = KnowledgeAgentService(settings=Settings(DYNAMIC_RETRIEVAL_ENABLED=False))
        request = OrchestrationRequest(question=COMPLEX, use_web_fallback=True)
        strategy = asyncio.run(service.decide(request, _route("vector", "bm25"), None))

        assert strategy.sources[0].top_k == Settings().top_k


class TestDeciderStrategiesAreStillBounded:
    """`_bounded` is a ceiling over untrusted decider output, not a default."""

    @staticmethod
    def _decider(top_k: int, sources: tuple[str, ...]):
        async def decide(request, route, plan, retry_feedback):
            return KnowledgeStrategy(
                sources=tuple(
                    KnowledgeSourcePlan(source=source, queries=("q",), top_k=top_k, timeout_ms=5_000)
                    for source in sources
                ),
                rationale="decider",
            )

        return decide

    def test_an_oversized_top_k_is_clamped_to_the_cap(self) -> None:
        service = KnowledgeAgentService(decider=self._decider(99, ("vector", "bm25")))
        strategy = asyncio.run(service.decide(OrchestrationRequest(question=SIMPLE), _route("vector", "bm25"), None))

        assert strategy.sources[0].top_k == Settings().dynamic_vector_top_k_cap

    def test_the_clamp_does_not_undo_complexity_scaling(self) -> None:
        """It used to clamp to `TOP_K`, which would cap a widened plan straight
        back down to the simple-query width."""
        assert Settings().dynamic_vector_top_k_cap > Settings().top_k

    def test_a_decider_cannot_exceed_the_plan_budget(self) -> None:
        service = KnowledgeAgentService(decider=self._decider(4, ("vector", "bm25", "graph", "web")))
        strategy = asyncio.run(
            service.decide(
                OrchestrationRequest(question=SIMPLE, use_web_fallback=True),
                _route("vector", "bm25", "graph", "web"),
                _plan(2),
            )
        )

        assert len(strategy.sources) == 2


class TestOrchestratorHonoursTheWidth:
    def test_the_strategy_decides_the_rerank_size_not_the_setting(self) -> None:
        """The field is new; without this the orchestrator keeps reading
        `RERANKER_TOP_N` and the widening stops at the Knowledge Agent."""
        from app.domain.contracts import EvidenceItem
        from app.domain.knowledge import AccessScope
        from app.knowledge.adapters import CallableKnowledgeAdapter
        from app.knowledge.orchestrator import KnowledgeOrchestrator, discard_trace
        from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

        async def many(plan, scope):
            return tuple(
                EvidenceItem(
                    content=f"chunk {index}",
                    source="/uploads/alice/notes.pdf",
                    document_id=f"doc-{index}",
                    version=1,
                    retriever="vector",
                )
                for index in range(9)
            )

        scope = AccessScope(
            tenant_id="alice",
            user_id="alice",
            role="viewer",
            allowed_sources=frozenset({"/uploads/alice/notes.pdf"}),
            allowed_fields=DEFAULT_CONTEXT_FIELDS,
        )
        strategy = KnowledgeStrategy(
            sources=(KnowledgeSourcePlan(source="vector", queries=("q",), top_k=9, timeout_ms=5_000),),
            rewrite=False,
            rerank=False,
            rerank_top_n=8,
            rationale="test",
        )
        orchestrator = KnowledgeOrchestrator(adapters={"vector": CallableKnowledgeAdapter("vector", many)})

        bundle = asyncio.run(orchestrator.retrieve(strategy, scope, discard_trace))

        assert bundle.diagnostics["rerank_top_n"] == 8
        assert bundle.diagnostics["post_rerank_count"] == 8


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (SIMPLE, 0),
        ("请对比 A 与 B", 1),
        (COMPLEX, 3),
    ],
)
def test_complexity_signal(query: str, expected: int) -> None:
    from app.knowledge.width import query_complexity

    assert query_complexity(query) == expected
