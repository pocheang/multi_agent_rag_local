"""Behavioral replacements for the retired graph-streaming test seam."""
import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, FinalAnswer, RouteDecision
from app.orchestration.compatibility_post_execution import StreamPostExecutionContext, StreamResultPostProcessor
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.request import OrchestrationRequest
from app.orchestration.standard_request_policy import prepare_standard_request
from app.services.retrieval.adaptive_policy import build_adaptive_plan
from app.services.retrieval.evidence_scoring import evidence_is_sufficient


def test_stream_prefers_effective_hit_count_for_web_fallback():
    assert not evidence_is_sufficient({"retrieved_count": 5, "effective_hit_count": 0}, {}, "vector", 1)


def test_stream_does_not_use_web_when_fallback_enabled_and_local_evidence_sufficient():
    assert evidence_is_sufficient({"retrieved_count": 3, "effective_hit_count": 3}, {}, "vector", 3)


def _engine(synthesizer=None):
    route = RouteDecision(confidence=1, requires_plan=False, allowed_capabilities=frozenset({"rag"}), reason="test")
    async def router(_request): return route
    async def planner(*_args): raise AssertionError("planning disabled")
    async def retriever(*_args): return EvidenceBundle()
    async def tools(*_args): raise AssertionError("tools disabled")
    async def synth(*_args): return FinalAnswer(answer="ok", route=route)
    return OrchestrationEngine(services=OrchestrationServices(router=router, planner=planner,
        retriever=retriever, tool_runner=tools, synthesizer=synthesizer or synth))


@pytest.mark.asyncio
async def test_stream_emits_thought_events():
    events = [e async for e in _engine().execute_stream(OrchestrationRequest(question="test"))]
    assert [(e["stage"], e["status"]) for e in events if e["type"] == "status"] == [
        ("route", "completed"), ("rag", "completed"), ("synthesize", "completed"),
        ("complete", "completed")]


@pytest.mark.asyncio
async def test_stream_continues_when_vector_retrieval_fails():
    async def vector(*_args): raise RuntimeError("vector down")
    async def bm25(*_args):
        return EvidenceBundle(items=(EvidenceItem(content="fallback", source="guide", document_id="guide"),))
    events = []
    async def report(event): events.append(event)
    service = RAGAgentService(vector=vector, bm25=bm25, report_degradation=report)
    route = RouteDecision(confidence=1, requires_plan=False, allowed_capabilities=frozenset({"rag"}), reason="test")
    result = await service.retrieve(OrchestrationRequest(question="test"), route, None)
    assert result.items[0].content == "fallback"
    assert any(e.status == "skipped" and "vector down" in e.message for e in events)


def test_stream_forces_web_when_user_explicitly_requests_online_search():
    assert build_adaptive_plan("search online", "vector", "answer", True, True).prefer_web is True


def test_stream_skips_web_for_casual_chat(monkeypatch):
    from app.orchestration import standard_request_policy
    monkeypatch.setattr(standard_request_policy, "is_casual_chat_query", lambda _q: True)
    prepared = prepare_standard_request(OrchestrationRequest(question="hello", use_web_fallback=True, use_reasoning=True))
    assert prepared.is_fast_smalltalk and not prepared.request.use_web_fallback and not prepared.request.use_reasoning


@pytest.mark.asyncio
async def test_stream_recovers_when_stream_synthesis_raises():
    async def broken(*_args): raise RuntimeError("synthesis down")
    with pytest.raises(Exception, match="synthesis down"):
        _ = [e async for e in _engine(broken).execute_stream(OrchestrationRequest(question="test"))]


def test_stream_partial_then_error_emits_answer_reset():
    processor = StreamResultPostProcessor(
        StreamPostExecutionContext(None, "test", "", False, None, "trace"), lambda _result: (None, None),
        enforce_source_scope=lambda result, _sources: result,
        resynthesize=lambda result, *_args: {**result, "answer": "fallback final"})
    final, reset = processor.finalize({"answer": "partial ", "vector_result": {}, "web_result": {}})
    assert reset == "fallback final" and final["answer"] == "fallback final"
