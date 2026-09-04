"""Build bounded structured dependency plans without mandatory LLM calls."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.agents.clarification.rules import assess_completeness
from app.core.config import Settings, get_settings
from app.domain.contracts import PlannedTask, RouteDecision, TaskBudget, TaskPlan
from app.orchestration.request import OrchestrationRequest

DecompositionResult = TaskPlan | tuple[str, ...]
QueryDecomposer = Callable[[str], Awaitable[DecompositionResult]]


class PlanLimitError(ValueError):
    """Raised when a generated DAG exceeds a configured execution boundary."""


@dataclass(frozen=True)
class PlannerLimits:
    max_tasks: int
    max_depth: int
    max_retrieval_budget: int
    max_tool_budget: int

    @classmethod
    def from_settings(cls, settings: Settings) -> PlannerLimits:
        return cls(
            max_tasks=settings.planner_max_tasks,
            max_depth=settings.planner_max_depth,
            max_retrieval_budget=settings.planner_max_retrieval_budget,
            max_tool_budget=settings.planner_max_tool_budget,
        )


class PlannerAgentService:
    """Create a small validated DAG and fail safely to one direct task."""

    def __init__(
        self,
        decompose: QueryDecomposer | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._decompose = decompose
        self._limits = PlannerLimits.from_settings(settings or get_settings())

    async def plan(self, request: OrchestrationRequest, route: RouteDecision) -> TaskPlan:
        """Plan only when useful; simple requests never invoke the decomposer."""

        if not route.requires_plan:
            return self._validated(_direct_plan(request.question, route))

        comparison = _comparison_plan(request.question, route)
        if comparison is not None:
            try:
                return self._validated(comparison)
            except PlanLimitError as exc:
                return self._validated(
                    _direct_plan(
                        request.question,
                        route,
                        fallback_reason=f"comparison_fallback:{type(exc).__name__}",
                    )
                )

        if self._decompose is None or not request.enable_decomposition:
            return self._validated(_direct_plan(request.question, route))

        try:
            decomposed = await self._decompose(request.question)
            if isinstance(decomposed, TaskPlan):
                candidate = decomposed
            elif isinstance(decomposed, tuple):
                candidate = _plan_queries(decomposed, route)
            else:
                raise TypeError("decomposer must return TaskPlan or tuple[str, ...]")
            return self._validated(candidate)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            fallback = _direct_plan(
                request.question,
                route,
                fallback_reason=f"decomposer_fallback:{type(exc).__name__}",
            )
            return self._validated(fallback)

    def _validated(self, plan: TaskPlan) -> TaskPlan:
        tasks = plan.tasks
        if len(tasks) > self._limits.max_tasks:
            raise PlanLimitError(f"plan exceeds max task count {self._limits.max_tasks}")
        depth = len(plan.execution_layers)
        if depth > self._limits.max_depth:
            raise PlanLimitError(f"plan exceeds max depth {self._limits.max_depth}")
        retrieval_budget = sum(task.budget.max_retrievals for task in tasks)
        if retrieval_budget > self._limits.max_retrieval_budget:
            raise PlanLimitError(f"plan exceeds retrieval budget {self._limits.max_retrieval_budget}")
        tool_budget = sum(task.budget.max_tool_calls for task in tasks)
        if tool_budget > self._limits.max_tool_budget:
            raise PlanLimitError(f"plan exceeds tool budget {self._limits.max_tool_budget}")
        return plan


def _comparison_plan(question: str, route: RouteDecision) -> TaskPlan | None:
    assessment = assess_completeness(question)
    if assessment.intent != "document_comparison":
        return None
    raw_targets = assessment.extracted_info.get("doc_ids", "")
    targets = tuple(value.strip() for value in raw_targets.split("、") if value.strip())
    if len(targets) < 2:
        return None
    retrieval_tasks = tuple(
        PlannedTask(
            # The bare target, not "Retrieve authoritative evidence about X".
            # These prompts are search queries now (see
            # `KnowledgeAgentService._source_plan`), and `bm25_search` matches on
            # shared term membership -- so the English boilerplate would make
            # every chunk containing "evidence" a candidate for a comparison that
            # is usually asked in Chinese. It also means the sub-queries the API
            # reports are the ones that were actually searched.
            task_id=f"retrieve-{index}",
            prompt=target,
            parallel_group="comparison-evidence",
            knowledge_required=True,
            tool_required=False,
            budget=TaskBudget(max_retrievals=_retrieval_budget(route), max_tool_calls=0),
        )
        for index, target in enumerate(targets[:6], start=1)
    )
    synthesis = PlannedTask(
        task_id="compare-results",
        prompt=question,
        depends_on=tuple(task.task_id for task in retrieval_tasks),
        knowledge_required=False,
        tool_required=False,
        budget=TaskBudget(max_retrievals=0, max_tool_calls=0),
    )
    return TaskPlan(tasks=(*retrieval_tasks, synthesis))


def _plan_queries(queries: Sequence[str], route: RouteDecision) -> TaskPlan:
    normalized = tuple(dict.fromkeys(str(query).strip() for query in queries if str(query).strip()))
    if not normalized:
        raise ValueError("decomposer returned no executable subtasks")
    if len(normalized) == 1:
        return _direct_plan(normalized[0], route)
    retrieval_tasks = tuple(
        PlannedTask(
            task_id=f"retrieve-{index}",
            prompt=query,
            parallel_group="decomposed-evidence",
            knowledge_required=True,
            tool_required=False,
            budget=TaskBudget(max_retrievals=_retrieval_budget(route), max_tool_calls=0),
        )
        for index, query in enumerate(normalized, start=1)
    )
    synthesis = PlannedTask(
        task_id="combine-results",
        prompt="Combine the retrieved subtask evidence to answer the original request.",
        depends_on=tuple(task.task_id for task in retrieval_tasks),
        knowledge_required=False,
        tool_required=route.intent == "tool_call",
        budget=TaskBudget(max_retrievals=0, max_tool_calls=1 if route.intent == "tool_call" else 0),
    )
    return TaskPlan(tasks=(*retrieval_tasks, synthesis))


def _direct_plan(
    question: str,
    route: RouteDecision,
    *,
    fallback_reason: str | None = None,
) -> TaskPlan:
    tool_required = route.intent == "tool_call"
    return TaskPlan(
        tasks=(
            PlannedTask(
                task_id="task-1",
                prompt=question,
                knowledge_required=True,
                tool_required=tool_required,
                budget=TaskBudget(
                    max_retrievals=_retrieval_budget(route),
                    max_tool_calls=1 if tool_required else 0,
                ),
            ),
        ),
        plan_fallback_reason=fallback_reason,
    )


def _retrieval_budget(route: RouteDecision) -> int:
    budget = 2  # Vector and BM25 are the standard local retrieval pair.
    if route.intent == "hybrid":
        budget += 1
    if "web" in route.allowed_capabilities:
        budget += 1
    return budget


async def default_llm_decompose(question: str) -> tuple[str, ...]:
    """Decompose a complex query into sub-queries with the real LLM-backed decomposer.

    Only reached when a request explicitly sets ``enable_decomposition=True`` (opt-in
    on ``OrchestrationRequest``); every other request keeps going through
    ``_direct_plan``/``_comparison_plan`` unaffected.
    """
    from app.services.models.runtime import get_reasoning_model
    from app.services.query.decomposer import QueryDecomposer

    decomposer = QueryDecomposer(get_reasoning_model(temperature=0.3))
    result = await decomposer.decompose(question)
    return tuple(result.sub_queries)


__all__ = ["PlanLimitError", "PlannerAgentService", "PlannerLimits", "default_llm_decompose"]
