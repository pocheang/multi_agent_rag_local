"""Pipeline stage events must land in the store the SSE endpoint reads.

Three independent breaks used to swallow them: RAGPipeline built the engine
without a publisher (so it fell back to NullEventPublisher), nothing but the
MCP registry ever wrote to ExecutionEventStore, and record_agent_step had no
callers. The net effect was that
GET /api/v1/orchestration/executions/{id}/events replayed exactly one
synthesized terminal event for an ordinary chat turn, so the frontend trace
panel had nothing to show.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.contracts import FinalAnswer, RouteDecision, TaskPlan, ValidationStatus
from app.domain.events import ExecutionEvent
from app.domain.workflow import ContextBundle
from app.orchestration.engine import OrchestrationServices
from app.orchestration.event_publisher import ExecutionStoreEventPublisher
from app.orchestration.execution_events import ExecutionEventStore, current_execution_id
from app.pipeline.contracts import PipelineRequest, PipelineUser
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline

ROUTE = RouteDecision(
    intent="knowledge_retrieval",
    route="vector",
    confidence=0.9,
    requires_plan=False,
    reason="stubbed route",
)


def _stub_services() -> OrchestrationServices:
    async def router(request):
        return ROUTE

    async def planner(request, route):
        return TaskPlan()

    async def retriever(request, route, plan, strategy, scope):
        return ContextBundle()

    async def tool_runner(request, route, plan):
        return ()

    async def synthesizer(request, route, plan, evidence, tool_results):
        return FinalAnswer(
            answer="stubbed answer",
            route=route,
            evidence=evidence,
            validation=ValidationStatus(state="validated", approved=True, method="stub"),
        )

    return OrchestrationServices(
        router=router,
        planner=planner,
        retriever=retriever,
        tool_runner=tool_runner,
        synthesizer=synthesizer,
    )


class _StubCapabilities:
    """Stand in for CoreCapabilities without touching models or retrieval."""

    typed_tools = None

    def orchestration_services(self) -> OrchestrationServices:
        return _stub_services()


async def _run(execution_id: str | None) -> None:
    await RAGPipeline(capabilities=_StubCapabilities()).execute(
        PipelineRequest(
            question="what does the store receive?",
            profile=PipelineProfile.ADVANCED,
            user=PipelineUser(user_id="u1", username="tester", role="admin"),
            execution_id=execution_id,
        )
    )


@pytest.mark.asyncio
async def test_publisher_files_events_under_the_bound_execution_id():
    """The unit the engine depends on: id from the ContextVar, event into the store."""
    store = ExecutionEventStore()
    publisher = ExecutionStoreEventPublisher(store)
    execution_id = "exec-store-test"

    token = current_execution_id.set(execution_id)
    try:
        await publisher.publish(ExecutionEvent(stage="knowledge", status="completed"))
        await publisher.publish(ExecutionEvent(stage="synthesize", status="completed"))
    finally:
        current_execution_id.reset(token)

    assert [event.stage for event in store.events_since(execution_id, 0)] == ["knowledge", "synthesize"]


@pytest.mark.asyncio
async def test_execute_publishes_more_than_one_stage_for_one_execution():
    from app.orchestration.execution_events import get_default_execution_event_store

    store = get_default_execution_event_store()
    execution_id = "exec-pipeline-roundtrip"
    await _run(execution_id)

    events = store.events_since(execution_id, 0)
    stages = [event.stage for event in events]
    assert len(events) > 1, f"expected a multi-stage trace, got {stages}"
    assert "knowledge" in stages, stages
    assert "synthesize" in stages, stages
    assert "complete" in stages, stages


@pytest.mark.asyncio
async def test_events_are_dropped_when_no_execution_id_is_bound():
    from app.orchestration.execution_events import get_default_execution_event_store

    store = get_default_execution_event_store()
    before = len(store.events_since("", 0))
    await _run(None)
    assert len(store.events_since("", 0)) == before


@pytest.mark.asyncio
async def test_concurrent_executions_do_not_share_a_stream():
    """The regression the shared _ENGINE_CACHE makes possible.

    A publisher holding the execution id as instance state would file whichever
    request bound it last, mixing request A's stages into request B's SSE
    stream. Reading it from a per-task ContextVar is what prevents that.
    """
    from app.orchestration.execution_events import get_default_execution_event_store

    store = get_default_execution_event_store()
    await asyncio.gather(_run("exec-concurrent-a"), _run("exec-concurrent-b"))

    a = store.events_since("exec-concurrent-a", 0)
    b = store.events_since("exec-concurrent-b", 0)
    assert len(a) > 1 and len(b) > 1
    assert len(a) == len(b), "one execution absorbed the other's events"


def test_store_evicts_least_recently_written_executions():
    store = ExecutionEventStore(max_executions=2)
    for name in ("first", "second", "third"):
        store.publish(name, ExecutionEvent(stage="route", status="completed"))

    assert store.events_since("first", 0) == ()
    assert len(store.events_since("second", 0)) == 1
    assert len(store.events_since("third", 0)) == 1


def test_store_caps_events_per_execution_without_shifting_offsets():
    store = ExecutionEventStore(max_events_per_execution=2)
    for stage in ("route", "knowledge", "synthesize"):
        store.publish("capped", ExecutionEvent(stage=stage, status="completed"))

    # The overflow event is dropped, not the oldest: a live subscriber holding
    # offset N must not have the events under it renumbered.
    assert [event.stage for event in store.events_since("capped", 0)] == ["route", "knowledge"]
