"""Current behavioral owners for retired graph-streaming contracts."""
import json
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.rag.service import RAGAgentService
from app.api.query.streaming import execution
from app.domain.contracts import EvidenceBundle, EvidenceItem, FinalAnswer, RouteDecision
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.request import OrchestrationRequest
from app.orchestration.standard_request_policy import prepare_standard_request
from app.pipeline.contracts import PipelineRequest
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline
from app.services.observability.agent_execution_tracker import AgentExecutionTracker


def _route(*, web=False):
    return RouteDecision(confidence=1, requires_plan=False,
        allowed_capabilities=frozenset({"rag", "web"} if web else {"rag"}), reason="test")


@pytest.mark.asyncio
async def test_stream_prefers_effective_hit_count_for_web_fallback():
    calls = []
    async def vector(*_args):
        return EvidenceBundle(items=(EvidenceItem(content="raw hit", source="local", document_id="local"),),
                              diagnostics={"retrieved_count": 5, "effective_hit_count": 0})
    async def empty(*_args): return EvidenceBundle()
    async def web(*_args):
        calls.append("web")
        return EvidenceBundle(items=(EvidenceItem(content="web", source="web", document_id="web"),))
    result = await RAGAgentService(vector=vector, bm25=empty, web=web).retrieve(
        OrchestrationRequest(question="test", use_web_fallback=True), _route(web=True), None)
    assert calls == ["web"]
    assert {item.source for item in result.items} == {"local", "web"}


@pytest.mark.asyncio
async def test_stream_does_not_use_web_when_fallback_enabled_and_local_evidence_sufficient():
    calls = []
    async def vector(*_args):
        return EvidenceBundle(items=(EvidenceItem(content="good", source="local", document_id="local"),),
                              diagnostics={"effective_hit_count": 3})
    async def empty(*_args): return EvidenceBundle()
    async def web(*_args): calls.append("web"); return EvidenceBundle()
    result = await RAGAgentService(vector=vector, bm25=empty, web=web).retrieve(
        OrchestrationRequest(question="test", use_web_fallback=True), _route(), None)
    assert calls == []
    assert [item.source for item in result.items] == ["local"]


def _engine(synthesizer=None):
    route = _route()
    async def router(_request): return route
    async def planner(*_args): raise AssertionError("planning disabled")
    async def retriever(*_args): return EvidenceBundle()
    async def tools(*_args): raise AssertionError("tools disabled")
    async def synth(*_args): return FinalAnswer(answer="ok", route=route)
    return OrchestrationEngine(services=OrchestrationServices(router=router, planner=planner,
        retriever=retriever, tool_runner=tools, synthesizer=synthesizer or synth))


@pytest.mark.asyncio
async def test_stream_emits_thought_events():
    pipeline = RAGPipeline(engine=_engine())
    events = [e async for e in pipeline.execute_stream(
        PipelineRequest(question="test", profile=PipelineProfile.STANDARD), execution_id="trace")]
    thought_events = [event for event in events if event["type"] == "thought"]
    assert thought_events, "typed RAGPipeline currently drops the supported thought-event contract (Task 7)"


@pytest.mark.asyncio
async def test_stream_continues_when_vector_retrieval_fails():
    async def vector(*_args): raise RuntimeError("implementation detail may change")
    async def bm25(*_args):
        return EvidenceBundle(items=(EvidenceItem(content="fallback", source="guide", document_id="guide"),))
    events = []
    async def report(event): events.append(event)
    result = await RAGAgentService(vector=vector, bm25=bm25, report_degradation=report).retrieve(
        OrchestrationRequest(question="test"), _route(), None)
    assert result.items[0].content == "fallback"
    assert any(e.stage == "rag" and e.status == "skipped" for e in events)
    assert any(e.stage == "rag" and e.status == "completed" for e in events)


def test_stream_forces_web_when_user_explicitly_requests_online_search(monkeypatch):
    from app.orchestration import standard_request_policy
    monkeypatch.setattr(standard_request_policy, "is_casual_chat_query", lambda _q: False)
    prepared = prepare_standard_request(OrchestrationRequest(
        question="search online", use_web_fallback=True, retrieval_strategy="advanced"))
    assert prepared.request.use_web_fallback is True


def test_stream_skips_web_for_casual_chat(monkeypatch):
    from app.orchestration import standard_request_policy
    monkeypatch.setattr(standard_request_policy, "is_casual_chat_query", lambda _q: True)
    prepared = prepare_standard_request(OrchestrationRequest(question="hello", use_web_fallback=True, use_reasoning=True))
    assert prepared.is_fast_smalltalk and not prepared.request.use_web_fallback and not prepared.request.use_reasoning


async def _api_events(monkeypatch, pipeline):
    execution_id = f"stream-{uuid4().hex}"
    AgentExecutionTracker.get_instance().start_execution("test", execution_id=execution_id, user_id="user")
    monkeypatch.setattr(execution.query_guard, "acquire", lambda _key: nullcontext())
    monkeypatch.setattr(execution, "_query_limiter_key", lambda *_args: "user")
    monkeypatch.setattr(execution, "_is_overload_mode", lambda: False)
    monkeypatch.setattr(execution.query_result_cache, "clear_inflight", lambda _key: None)
    context = execution.StreamExecutionContext(
        request=SimpleNamespace(state=SimpleNamespace(trace_id="trace"), headers={}), user={"user_id": "user"},
        session_id=None, original_question="test", effective_question="test", normalized_strategy=None,
        strategy_meta={}, stream_cache_key=execution_id, replay_enabled=False, runtime_api_settings=None,
        execution_id=execution_id, history_store=None, pipeline=pipeline,
        pipeline_request=PipelineRequest(question="test", profile=PipelineProfile.STANDARD),
        preparation=None, source_scope_audit=lambda *_args: None, result_signer=lambda *_args: (None, None))
    chunks = [chunk async for chunk in execution.stream_execution_events(context)]
    return [json.loads(chunk.removeprefix("data: ").strip()) for chunk in chunks]


@pytest.mark.asyncio
async def test_stream_recovers_when_stream_synthesis_raises(monkeypatch):
    async def broken(*_args): raise RuntimeError("synthesis down")
    events = await _api_events(monkeypatch, RAGPipeline(engine=_engine(broken)))
    assert events[-1]["type"] == "error"
    assert events[-1]["error"] == "internal_error"
    assert not any(event["type"] == "done" for event in events)


@pytest.mark.asyncio
async def test_stream_partial_then_error_emits_answer_reset(monkeypatch):
    class PartialThenBrokenPipeline:
        async def execute_stream(self, *_args, **_kwargs):
            yield {"type": "answer_chunk", "content": "partial "}
            raise RuntimeError("stream broken")
    events = await _api_events(monkeypatch, PartialThenBrokenPipeline())
    assert [event["type"] for event in events][-2:] == ["answer_chunk", "error"]
    assert events[-2]["content"] == "partial "
    assert events[-1]["error"] == "internal_error"
    assert not any(event["type"] == "done" for event in events)
