"""The planner's sub-queries must reach the retrievers.

The planner has produced sub-queries for a long time -- `_plan_queries` for a
decomposed request, `_comparison_plan` for a comparison -- and every one of them
died in `PlannedTask.prompt`. Grepping `app/`, that field had exactly one reader,
`rag_pipeline.py`, and only to build a diagnostics dict.

The chain was broken in two places at once: `KnowledgeAgentService._source_plan`
hardcoded `queries=(query,)`, and `RAGAgentService.retrieve` opened with
`del plan`. So a decomposed question ran one search on the original wording,
while the API returned the sub-queries to the client as `decomposed_query` --
reporting work that never happened.

The downstream plumbing was always fine: every adapter in
`app/knowledge/adapters.py` already fans out over `plan.queries`.
"""

from __future__ import annotations

import pytest

from app.agents.knowledge.service import MAX_PLAN_QUERIES_PER_SOURCE, KnowledgeAgentService
from app.agents.planner.service import PlannerAgentService
from app.domain.contracts import PlannedTask, RouteDecision, TaskBudget, TaskPlan
from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import RouterDecision, VerificationDecision
from app.orchestration.request import OrchestrationRequest

_QUESTION = "总体成本是多少"


def _scope() -> AccessScope:
    return AccessScope(
        tenant_id="t1",
        user_id="u1",
        role="viewer",
        allowed_sources=frozenset({"/docs/a.md"}),
    )


def _route() -> RouterDecision:
    return RouterDecision(
        intent="knowledge_retrieval",
        complexity="complex",
        completeness="complete",
        next_stage="knowledge",
        confidence=0.9,
        reason="test",
    )


def _retrieval_task(task_id: str, prompt: str) -> PlannedTask:
    return PlannedTask(
        task_id=task_id,
        prompt=prompt,
        parallel_group="decomposed-evidence",
        knowledge_required=True,
        budget=TaskBudget(max_retrievals=2, max_tool_calls=0),
    )


def _decomposed_plan(*prompts: str) -> TaskPlan:
    retrieval = tuple(_retrieval_task(f"retrieve-{i}", p) for i, p in enumerate(prompts, start=1))
    synthesis = PlannedTask(
        task_id="combine-results",
        prompt="Combine the retrieved subtask evidence to answer the original request.",
        depends_on=tuple(task.task_id for task in retrieval),
        knowledge_required=False,
        budget=TaskBudget(max_retrievals=0, max_tool_calls=0),
    )
    return TaskPlan(tasks=(*retrieval, synthesis))


def _decide(
    plan: TaskPlan | None,
    *,
    question: str = _QUESTION,
    retry=None,
    use_web_fallback: bool = False,
) -> KnowledgeStrategy:
    import asyncio

    service = KnowledgeAgentService(available_sources={"vector", "bm25", "web"})
    request = OrchestrationRequest(question=question, use_web_fallback=use_web_fallback)
    return asyncio.run(service.decide(request, _route(), plan, retry, _scope()))


def _queries_for(strategy: KnowledgeStrategy, source: str) -> tuple[str, ...]:
    return next(plan.queries for plan in strategy.sources if plan.source == source)


def test_a_decomposed_plan_seeds_every_sub_query_into_the_local_source_plans():
    """The assertion that would have caught it: today this returned `(question,)`."""

    strategy = _decide(_decomposed_plan("硬件成本", "人力成本"))

    assert _queries_for(strategy, "vector") == (_QUESTION, "硬件成本", "人力成本")
    assert _queries_for(strategy, "bm25") == (_QUESTION, "硬件成本", "人力成本")


def test_the_original_question_stays_at_index_zero():
    """`KnowledgeOrchestrator` reads `sources[0].queries[0]` as `primary_query`,
    the one string reranking scores every candidate against, and as the rewrite
    input. A sub-query there would rerank the whole result set against one facet.
    """

    strategy = _decide(_decomposed_plan("硬件成本", "人力成本"))

    assert strategy.sources[0].queries[0] == _QUESTION


def test_the_synthesis_task_is_not_a_retrieval_query():
    """Its prompt is an instruction to a model, not text to search for; it is the
    one task with `knowledge_required=False`."""

    strategy = _decide(_decomposed_plan("硬件成本"))

    assert not any("Combine the retrieved" in query for query in _queries_for(strategy, "vector"))


def test_a_direct_plan_does_not_duplicate_the_question():
    """A direct plan's single task prompt *is* the original question, and
    `reciprocal_rank_fuse` accumulates a contribution per appearance -- so a
    duplicate would silently double-weight everything it returned."""

    direct = TaskPlan(tasks=(_retrieval_task("task-1", _QUESTION),))

    assert _queries_for(_decide(direct), "vector") == (_QUESTION,)


def test_no_plan_searches_only_the_question():
    assert _queries_for(_decide(None), "vector") == (_QUESTION,)


def test_sub_queries_are_capped():
    plan = _decomposed_plan("一", "二", "三", "四", "五", "六")

    assert len(_queries_for(_decide(plan), "vector")) == MAX_PLAN_QUERIES_PER_SOURCE


def test_web_is_not_fanned_out_over_sub_queries():
    """`_retrieve_web` calls `run_web_research` once per query, and concurrent
    `DDGS()` construction has wedged this process at zero CPU before."""

    strategy = _decide(
        _decomposed_plan("硬件成本", "人力成本"),
        question="今天的最新价格是多少",
        use_web_fallback=True,
    )

    # The local sources got the sub-queries; web got the question alone.
    assert _queries_for(strategy, "vector") == ("今天的最新价格是多少", "硬件成本", "人力成本")
    assert _queries_for(strategy, "web") == ("今天的最新价格是多少",)


def test_a_verifier_retry_keeps_its_own_query_first():
    """The retry query is what the verifier asked to be searched, so it takes the
    slot `primary_query` reads."""

    retry = VerificationDecision(status="retry_retrieval", retry_query="成本明细")

    strategy = _decide(_decomposed_plan("硬件成本"), retry=retry)

    assert _queries_for(strategy, "vector") == ("成本明细", "硬件成本")


def test_a_decider_cannot_return_an_unbounded_query_list():
    """`KnowledgeSourcePlan.queries` has a min_length and no max, and `_bounded`
    never inspected it."""

    import asyncio

    async def greedy(request, route, plan, retry):
        return KnowledgeStrategy(
            sources=(
                KnowledgeSourcePlan(
                    source="vector",
                    queries=tuple(f"q{i}" for i in range(50)),
                    top_k=4,
                    timeout_ms=1000,
                ),
            ),
            rationale="greedy decider",
        )

    service = KnowledgeAgentService(decider=greedy, available_sources={"vector", "bm25"})
    strategy = asyncio.run(service.decide(OrchestrationRequest(question=_QUESTION), _route(), None, None, _scope()))

    assert len(strategy.sources[0].queries) == MAX_PLAN_QUERIES_PER_SOURCE


@pytest.mark.asyncio
async def test_a_comparison_plan_searches_the_target_not_the_instruction():
    """`_comparison_plan` used to emit "Retrieve authoritative evidence about X".

    `bm25_search` matches on shared term membership, so that English boilerplate
    would make every chunk containing "evidence" a candidate -- for a comparison
    usually asked in Chinese.
    """

    route = RouteDecision(
        intent="knowledge_retrieval",
        route="vector",
        confidence=0.9,
        requires_plan=True,
        reason="test",
    )
    plan = await PlannerAgentService().plan(
        OrchestrationRequest(question="比较 方案A、方案B 的差异"),
        route,
    )

    retrieval_prompts = [task.prompt for task in plan.tasks if task.knowledge_required]

    assert retrieval_prompts, "the comparison plan must produce retrieval tasks"
    assert all("Retrieve authoritative evidence" not in prompt for prompt in retrieval_prompts)
