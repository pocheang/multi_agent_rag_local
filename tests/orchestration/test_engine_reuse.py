"""A shared engine must keep each request's events in its own stream.

RAGPipeline used to build a fresh OrchestrationEngine (and recompile the
LangGraph workflow, ~20ms of synchronous CPU work) per request. Caching it is
only safe because OrchestrationServices scopes its event reporter with a
ContextVar; with the old instance attribute, request B's bind_event_reporter
overwrote request A's and A's execution events landed in B's SSE stream.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.events import ExecutionEvent
from app.orchestration.engine import OrchestrationServices
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


def _services() -> OrchestrationServices:
    async def unused(*args, **kwargs):
        raise AssertionError("not called in this test")

    return OrchestrationServices(
        router=unused, planner=unused, retriever=unused, tool_runner=unused, synthesizer=unused
    )


@pytest.mark.asyncio
async def test_concurrent_tasks_do_not_share_the_event_reporter():
    services = _services()
    seen: dict[str, list[str]] = {"a": [], "b": []}

    async def run(name: str) -> None:
        async def reporter(event: ExecutionEvent) -> None:
            seen[name].append(f"{name}:{event.stage}")

        services.bind_event_reporter(reporter)
        await asyncio.sleep(0)  # force interleaving with the other task
        await services.report_event(ExecutionEvent(stage="route", status="completed"))

    await asyncio.gather(run("a"), run("b"))

    assert seen["a"] == ["a:route"]
    assert seen["b"] == ["b:route"]


@pytest.mark.asyncio
async def test_report_event_is_a_noop_without_a_bound_reporter():
    await _services().report_event(ExecutionEvent(stage="route", status="completed"))


def test_default_pipelines_share_one_engine():
    first = RAGPipeline()._engine_for(PipelineProfile.ADVANCED)
    second = RAGPipeline()._engine_for(PipelineProfile.ADVANCED)
    assert first is second


def test_custom_capabilities_get_a_private_engine():
    from app.orchestration.capabilities import CoreCapabilities

    shared = RAGPipeline()._engine_for(PipelineProfile.ADVANCED)
    custom = RAGPipeline(capabilities=CoreCapabilities())._engine_for(PipelineProfile.ADVANCED)
    assert custom is not shared


def test_injected_engine_bypasses_the_cache():
    sentinel = object()
    assert RAGPipeline(engine=sentinel)._engine_for(PipelineProfile.ADVANCED) is sentinel
