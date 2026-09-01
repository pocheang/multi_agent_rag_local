"""A stage that runs out of time must degrade, not fail the request.

Every stage ceiling used to be unconditional: `run_with_timeout` raised, nothing
caught it, and the API turned it into a bare 500 -- even where a usable answer
was already available (an unverified answer, an answer with no evidence, a route
the legacy router would itself have defaulted to). The two exceptions are the
security boundaries: skipping scope resolution or output DLP is a hole, not a
degradation, so those still fail closed.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision, TaskPlan
from app.domain.events import ExecutionEvent
from app.domain.knowledge import AccessScope
from app.domain.workflow import CandidateAnswer, ContextBundle, RouterDecision, VerificationDecision
from app.orchestration.langgraph.nodes import WorkflowNodeRuntime
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import (
    MANDATORY_STAGES,
    ExecutionBudget,
    StageTimeoutError,
    TimeoutConfig,
)
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

_REQUEST = OrchestrationRequest(question="what is in the report?")
_ROUTE = RouteDecision(
    intent="knowledge_retrieval",
    route="vector",
    confidence=0.9,
    requires_plan=False,
    allowed_capabilities=frozenset({"rag"}),
    reason="test",
)
_ROUTE_DECISION = RouterDecision(
    intent="knowledge_retrieval",
    complexity="simple",
    completeness="complete",
    next_stage="knowledge",
    confidence=0.9,
    reason="test",
)
_SCOPE = AccessScope(
    tenant_id="t1",
    user_id="u1",
    role="viewer",
    allowed_sources=frozenset({"a.pdf"}),
    allowed_fields=DEFAULT_CONTEXT_FIELDS,
)


def _tight_config() -> TimeoutConfig:
    """Ceilings small enough that a hanging stage trips them immediately."""
    return TimeoutConfig(
        total_timeout_ms=10_000,
        route_timeout_ms=40,
        plan_timeout_ms=40,
        retrieval_timeout_ms=40,
        tool_timeout_ms=40,
        synthesis_timeout_ms=40,
        finalization_timeout_ms=40,
        overhead_buffer_ms=0,
    )


async def _hang(*_args, **_kwargs):
    await asyncio.sleep(30)


async def _discard(_event: object) -> None:
    return None


def _runtime(**services) -> WorkflowNodeRuntime:
    return WorkflowNodeRuntime(
        services=SimpleNamespace(**services),
        policy=ExecutionPolicy(),
        max_verifier_retries=1,
        context_token_budget=2_000,
    )


def _state(config: TimeoutConfig | None = None, **extra) -> dict:
    return {
        "request": _REQUEST,
        "budget": ExecutionBudget(config or _tight_config()),
        "reporter": _discard,
        **extra,
    }


# --- the mechanism ----------------------------------------------------------


@pytest.mark.asyncio
async def test_a_stage_without_a_fallback_still_fails_the_request():
    """No on_timeout means fail closed; that is the contract the two security
    stages rely on."""
    runtime = _runtime()

    with pytest.raises(StageTimeoutError):
        await runtime._run_stage(
            _state(),
            event_stage="output_filter",
            timeout_stage="output_filter",
            operation=_hang,
            expected_type=object,
        )


@pytest.mark.asyncio
async def test_a_degraded_stage_reports_a_failed_event_the_diagnostics_can_see():
    """`summarize_workflow_execution` collects `failed` events and any
    `failure_reason` metadata into execution_metadata, so a degraded run is
    visible to the caller instead of looking like a clean one."""
    reported: list[ExecutionEvent] = []

    async def capture(event: ExecutionEvent) -> None:
        reported.append(event)

    runtime = _runtime()
    state = _state()
    state["reporter"] = capture

    result, event = await runtime._run_stage(
        state,
        event_stage="synthesize",
        timeout_stage="synthesize",
        operation=_hang,
        expected_type=object,
        on_timeout=lambda: "fallback",
    )

    assert result == "fallback"
    assert event.status == "failed"
    assert {item.key: item.value for item in event.metadata}["failure_reason"] == "stage_timeout:synthesize"
    assert reported == [event]


# --- per-stage fallbacks ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_router_timeout_falls_back_to_the_safe_local_route():
    runtime = _runtime(router=_hang)

    result = await runtime.router(_state())

    assert result["route"].effective_route == "vector"
    assert result["route"].reason == "route_timeout_safe_default"
    assert result["route"].requires_plan is False
    assert result["route_decision"].next_stage == "knowledge"


@pytest.mark.asyncio
async def test_a_planner_timeout_continues_with_no_plan():
    runtime = _runtime(planner=_hang)

    result = await runtime.planner(_state(route=_ROUTE))

    assert "task_plan" not in result


@pytest.mark.asyncio
async def test_a_retrieval_timeout_continues_with_no_evidence():
    async def strategy(*_args, **_kwargs):
        raise AssertionError("not reached")

    runtime = _runtime(
        knowledge_agent=_hang,
        retriever=_hang,
        knowledge_orchestrator=None,
        tool_runner=strategy,
    )

    result = await runtime.knowledge(_state(route=_ROUTE, route_decision=_ROUTE_DECISION, permission_scope=_SCOPE))

    assert result["evidence_bundle"].items == ()
    assert result["context"].evidence == ()
    # The strategy timed out too, and fell back to the local pair.
    assert [plan.source for plan in result["knowledge_strategy"].sources] == ["vector", "bm25"]


@pytest.mark.asyncio
async def test_a_synthesis_timeout_returns_the_same_message_synthesis_itself_would():
    from app.agents.synthesizer.generation import SYNTHESIS_FALLBACK_MESSAGE

    runtime = _runtime(candidate_synthesizer=_hang)

    result = await runtime.synthesizer(_state(context=ContextBundle()))

    assert result["candidate_answer"].text == SYNTHESIS_FALLBACK_MESSAGE
    assert result["candidate_answer"].unresolved_items == ("synthesis_timeout",)


@pytest.mark.asyncio
async def test_a_verifier_timeout_degrades_the_answer_instead_of_dropping_it():
    item = EvidenceItem(content="text", source="a.pdf", document_id="a.pdf", version=1, retriever="vector")
    evidence = EvidenceBundle(items=(item,))
    runtime = _runtime(verifier=_hang, finalizer=None)

    result = await runtime.verifier(
        _state(
            route=_ROUTE,
            evidence_bundle=evidence,
            context=ContextBundle(evidence=(item,)),
            candidate_answer=CandidateAnswer(text="an answer"),
        )
    )

    assert result["verification"].status == "degraded"
    assert "verification timed out" in result["verification"].missing_aspects
    assert result["final_answer"].answer == "an answer"
    assert result["final_answer"].validation.state == "degraded"


# --- the budget ------------------------------------------------------------


def test_the_security_stages_are_exempt_from_a_spent_budget():
    """Clamping them to a spent budget would give them 0ms and turn each into an
    instant failure -- which for output DLP would be the request failing after
    the answer was already produced."""
    budget = ExecutionBudget(TimeoutConfig(total_timeout_ms=0))

    assert budget.remaining_ms() == 0
    for stage in MANDATORY_STAGES:
        budget.check_budget(stage)  # must not raise
        assert budget.get_stage_timeout(stage) > 0

    with pytest.raises(StageTimeoutError):
        budget.check_budget("synthesize")


def test_the_total_budget_gate_actually_fires():
    """`check_budget` used to reduce to `remaining_ms() >= 0`, which
    `remaining_ms`'s own max(0, ...) makes always true: the gate never fired."""
    spent = ExecutionBudget(TimeoutConfig(total_timeout_ms=0))
    unspent = ExecutionBudget(TimeoutConfig(total_timeout_ms=60_000))

    with pytest.raises(StageTimeoutError):
        spent.check_budget("knowledge")
    unspent.check_budget("knowledge")  # must not raise


@pytest.mark.asyncio
async def test_a_retry_the_clock_cannot_pay_for_is_downgraded_not_started():
    """A retry replays retrieval + synthesis + verification. Started without room
    for all three it used to run into the total-budget check and turn a merely
    degraded answer into a failed request."""

    async def wants_retry(*_args, **_kwargs) -> VerificationDecision:
        return VerificationDecision(
            status="retry_retrieval",
            retry_query="find more",
            missing_aspects=("needs more evidence",),
        )

    config = TimeoutConfig(
        total_timeout_ms=1_000,
        retrieval_timeout_ms=400,
        synthesis_timeout_ms=400,
        finalization_timeout_ms=400,
    )
    assert config.retry_round_ms() > config.total_timeout_ms

    runtime = _runtime(verifier=wants_retry, finalizer=None)
    result = await runtime.verifier(
        _state(
            config,
            route=_ROUTE,
            evidence_bundle=EvidenceBundle(),
            context=ContextBundle(),
            candidate_answer=CandidateAnswer(text="an answer"),
        )
    )

    assert result["verification"].status == "degraded"
    assert "insufficient time budget for verifier retry" in result["verification"].missing_aspects
    assert "final_answer" in result


@pytest.mark.asyncio
async def test_a_retry_the_clock_can_pay_for_still_happens():
    async def wants_retry(*_args, **_kwargs) -> VerificationDecision:
        return VerificationDecision(status="retry_retrieval", retry_query="find more")

    config = TimeoutConfig(
        total_timeout_ms=120_000,
        retrieval_timeout_ms=1_000,
        synthesis_timeout_ms=1_000,
        finalization_timeout_ms=1_000,
    )
    runtime = _runtime(verifier=wants_retry, finalizer=None)

    result = await runtime.verifier(
        _state(
            config,
            route=_ROUTE,
            evidence_bundle=EvidenceBundle(),
            context=ContextBundle(),
            candidate_answer=CandidateAnswer(text="an answer"),
        )
    )

    assert result["verification"].status == "retry_retrieval"
    assert result["retry_count"] == 1


# --- the configured values -------------------------------------------------


def test_the_shipped_ceilings_are_internally_consistent():
    from app.core.config import get_settings

    config = TimeoutConfig.from_settings(get_settings())  # raises if the sum overflows total

    assert config.stage_sum_ms() <= config.total_timeout_ms


def test_one_source_cannot_outlive_the_retrieval_stage_that_awaits_it():
    """A 30s per-source timeout under a 10s stage ceiling could never fire: the
    stage killed the request first, so the inner bound was decoration."""
    from app.agents.rag.service import _default_retriever_timeout
    from app.core.config import get_settings

    config = TimeoutConfig.from_settings(get_settings())

    assert _default_retriever_timeout() * 1000 < config.retrieval_timeout_ms


def test_a_plan_timeout_is_not_treated_as_a_planned_task():
    """`should_run_tools` needs a plan; the degraded path must not invent one."""
    assert ExecutionPolicy().should_run_tools(_ROUTE, None) is False
    assert TaskPlan is not None  # imported for the contract this asserts about
