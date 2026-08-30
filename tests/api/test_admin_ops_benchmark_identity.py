"""Admin ops benchmark and replay runs must carry the requesting admin's identity.

``_execute_standard_profile`` used to call the standard pipeline contract with no
``user``, so ``PipelineRequest.user`` was None, ``OrchestrationRequest.actor`` was
None, and the very first graph node -- ``privacy_permission`` -- aborted the run with
``AccessScopeError("authenticated user identity is required")``.  Every benchmark and
replay query therefore failed before reaching the router.

These tests run the real orchestration graph (real ``PrivacyService``, real
``AccessScopeResolver``) with only the LLM/retrieval leaves stubbed, so they fail on a
missing actor exactly the way the endpoints did.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes.admin import ops
from app.api.routes.internal import pipeline_contract
from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ValidationStatus
from app.orchestration.engine import OrchestrationServices
from app.pipeline.rag_pipeline import RAGPipeline

ADMIN = {"user_id": "admin-1", "username": "ops-admin", "role": "admin", "permissions": ["admin:ops_manage"]}

ROUTE = RouteDecision(
    intent="knowledge_retrieval",
    route="vector",
    confidence=0.9,
    requires_plan=False,
    reason="stubbed route",
)


def _stub_services() -> OrchestrationServices:
    """Stub only the leaves; privacy and access-scope stay the production objects."""

    async def router(request):
        return ROUTE

    async def planner(request, route):
        return TaskPlan()

    async def retriever(request, route, plan):
        return EvidenceBundle(route=route, plan=plan)

    async def tool_runner(request, route, plan, evidence):
        return ()

    async def synthesizer(request, route, plan, evidence, tool_results):
        return FinalAnswer(
            answer=f"stubbed answer to: {request.question}",
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


class _CapturingQueue:
    """Stand in for BackgroundTaskQueue; records the job instead of running it."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def submit(self, fn: Any, **kwargs: Any) -> bool:
        self.calls.append((fn, kwargs))
        return True


class _Request:
    """Minimal stand-in for starlette Request; only reached by audit helpers."""

    client = None
    headers: dict[str, str] = {}
    url = type("U", (), {"path": "/api/v1/admin/ops/benchmark/run"})()


@pytest.fixture
def stub_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_contract, "RAGPipeline", lambda: RAGPipeline(capabilities=_StubCapabilities()))


@pytest.fixture
def queue(monkeypatch) -> _CapturingQueue:
    captured = _CapturingQueue()
    monkeypatch.setattr(ops.api_dependencies, "get_query_runtime", lambda: type("R", (), {"shadow_queue": captured})())
    monkeypatch.setattr(ops, "_require_permission", lambda *a, **k: None)
    monkeypatch.setattr(ops, "_audit", lambda *a, **k: None)
    return captured


def test_benchmark_query_completes_under_an_admin_identity(stub_pipeline):
    result = ops._execute_standard_profile("what does the benchmark measure?", user=ADMIN)

    assert result["answer"] == "stubbed answer to: what does the benchmark measure?"
    assert result["route"] == "vector"


def test_missing_identity_still_fails_closed(stub_pipeline):
    """The guard the fix threads an identity past must stay in place."""
    with pytest.raises(Exception, match="authenticated user identity is required"):
        ops._execute_standard_profile("no actor", user={})


def test_benchmark_endpoint_hands_the_queue_an_identified_executor(stub_pipeline, queue):
    ops.admin_ops_benchmark_run(_Request(), max_queries=1, user=ADMIN)

    fn, kwargs = queue.calls[0]
    assert fn is ops.run_benchmark
    assert kwargs["execute_query"]("benchmark question")["answer"].startswith("stubbed answer")


def test_replay_endpoint_hands_the_queue_an_identified_executor(stub_pipeline, queue, monkeypatch):
    monkeypatch.setattr(ops, "_history_store_for_user", lambda user: object())

    ops.admin_ops_replay_run({"max_questions": 1}, _Request(), user=ADMIN)

    fn, kwargs = queue.calls[0]
    assert fn is ops.run_replay
    assert kwargs["execute_query"]("replay question")["answer"].startswith("stubbed answer")
