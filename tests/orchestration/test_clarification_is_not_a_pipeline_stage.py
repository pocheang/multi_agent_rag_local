"""Clarification is an HTTP conversation, not a pipeline stage.

There was a `clarification` node between `router` and `planner`. It spent a
`route_timeout_ms` ceiling and one clarifier call on every question with missing
fields, and produced two state values -- `clarification` and `complete_query` --
that nothing in `app/` ever read.

It could not have done otherwise. The multi-round state lives in the session
store behind `POST /api/v1/clarification/check`, so a graph node has no collected
context to pass; the clarifier therefore always returned `action="ask"`, which
the node logged and ignored, continuing with the original question.

What must survive the removal is the *information*: `RouteDecision.clarification_fields`
still says what is missing, `RouterDecision.completeness` still reports it, and
the HTTP endpoint still owns the interaction. That is what these tests pin --
a deletion that quietly took the feature with the no-op would look identical
from the graph's side.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.router.service import RouterAgentService
from app.core.config import get_settings
from app.domain.events import EventStage
from app.domain.workflow import RouterDecision
from app.orchestration.langgraph.nodes import WorkflowNodeRuntime
from app.orchestration.langgraph.workflow import build_workflow
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import ExecutionBudget, TimeoutConfig

# A comparison question with no documents named: `assess_completeness` reports
# `document_comparison` with `doc_ids` missing, which is what used to route here.
_INCOMPLETE = "对比一下这两个方案的成本"


async def _discard(_event: object) -> None:
    return None


def _runtime(**services) -> WorkflowNodeRuntime:
    return WorkflowNodeRuntime(
        services=SimpleNamespace(**services),
        policy=ExecutionPolicy(),
        max_verifier_retries=1,
        context_token_budget=2_000,
    )


async def _route(question: str) -> RouterDecision:
    request = OrchestrationRequest(question=question)
    runtime = _runtime(router=RouterAgentService().route)
    state = {
        "request": request,
        "budget": ExecutionBudget(TimeoutConfig.from_settings(get_settings())),
        "reporter": _discard,
    }
    return (await runtime.router(state))["route_decision"]


@pytest.mark.asyncio
async def test_a_question_with_missing_fields_goes_straight_to_planning():
    decision = await _route(_INCOMPLETE)

    assert decision.next_stage in {"planner", "knowledge"}
    assert decision.next_stage != "clarification"


@pytest.mark.asyncio
async def test_the_missing_fields_still_reach_the_caller():
    """The guard that the deletion removed the no-op and not the feature."""

    decision = await _route(_INCOMPLETE)

    assert decision.completeness == "incomplete"


@pytest.mark.asyncio
async def test_a_complete_question_is_still_reported_complete():
    """The negative direction, so the test above cannot pass by the router
    marking everything incomplete."""

    decision = await _route("什么是检索增强生成？")

    assert decision.completeness == "complete"


def test_the_graph_has_no_clarification_node():
    workflow = build_workflow(SimpleNamespace(), policy=ExecutionPolicy())

    assert "clarification" not in workflow.get_graph().nodes


def test_no_stage_budget_is_spent_on_clarification():
    """A named ceiling is a stage that runs. With the entry removed,
    "clarification" is just an unrecognised stage name like any other."""

    budget = ExecutionBudget(TimeoutConfig.from_settings(get_settings()))

    assert budget.get_stage_timeout("clarification") == budget.get_stage_timeout("not_a_stage_at_all")
    # And a stage that does still exist keeps a ceiling of its own, so the
    # assertion above cannot pass by every stage falling to the default.
    assert budget.get_stage_timeout("route") != budget.get_stage_timeout("not_a_stage_at_all")


def test_clarification_is_not_a_declared_event_stage():
    """`EventStage` and the frontend's EXECUTION_STAGES are documented as having
    to agree; an unknown stage makes the UI drop the event silently."""

    from typing import get_args

    assert "clarification" not in get_args(EventStage)


def test_the_frontend_stage_list_still_mirrors_the_backend():
    """The two lists are kept in sync by hand, which is why this is checked."""

    from pathlib import Path
    from typing import get_args

    source = Path("frontend/src/features/execution-trace/types.ts").read_text(encoding="utf-8")
    block = source.split("EXECUTION_STAGES = [", 1)[1].split("]", 1)[0]
    frontend_stages = tuple(line.strip().strip(',"') for line in block.splitlines() if line.strip())

    assert frontend_stages == get_args(EventStage)


def test_the_http_clarification_endpoint_still_works():
    """The interaction moved nowhere: it was always here."""

    from app.api.routes.public import clarification as endpoint

    assert endpoint.router.prefix == "/api/v1/clarification"
    assert any(getattr(route, "path", "").endswith("/check") for route in endpoint.router.routes)
