"""Build typed dependency plans from optional legacy query decomposition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.contracts import PlannedTask, RouteDecision, TaskBudget, TaskPlan
from app.orchestration.request import OrchestrationRequest

QueryDecomposer = Callable[[str], Awaitable[tuple[str, ...]]]


class PlannerAgentService:
    """Create a bounded TaskPlan without exposing decomposer implementation details."""

    def __init__(self, decompose: QueryDecomposer | None = None) -> None:
        self._decompose = decompose or _direct_task

    async def plan(self, request: OrchestrationRequest, route: RouteDecision) -> TaskPlan:
        """Convert decomposed queries into a deterministic dependency chain."""
        queries = await self._decompose(request.question)
        tasks = tuple(
            PlannedTask(
                task_id=f"task-{index}",
                prompt=query,
                depends_on=(f"task-{index - 1}",) if index > 1 else (),
                retrieval_required=True,
                tool_required=route.intent == "tool_call",
                budget=TaskBudget(max_retrievals=_retrieval_budget(route), max_tool_calls=1 if route.intent == "tool_call" else 0),
            )
            for index, query in enumerate(queries, start=1)
        )
        return TaskPlan(tasks=tasks)


def _retrieval_budget(route: RouteDecision) -> int:
    budget = 2  # Vector and BM25 are the standard local retrieval pair.
    if route.intent == "hybrid":
        budget += 1
    if "web" in route.allowed_capabilities:
        budget += 1
    return budget


async def _direct_task(question: str) -> tuple[str, ...]:
    """Use one deterministic task until an explicit decomposer is injected."""
    return (question,)
