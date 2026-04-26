import importlib
import sys
import types

import app.agents.router_agent as router_agent
import app.agents.synthesis_agent as synthesis_agent
from app.core.models import LocalEvidenceChatModel


def test_router_falls_back_when_model_invoke_fails(monkeypatch):
    class BrokenModel:
        def invoke(self, _messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(router_agent, "get_reasoning_model", lambda: BrokenModel())
    monkeypatch.setattr(router_agent, "get_chat_model", lambda: BrokenModel())
    monkeypatch.setattr(router_agent, "classify_agent_class", lambda _q: "general")

    decision = router_agent.decide_route("test", use_reasoning=True)
    assert decision.route == "vector"
    assert decision.skill == "answer_with_citations"
    assert "router_invoke_error" in decision.reason


def test_router_falls_back_when_model_build_fails(monkeypatch):
    def _raise_build_error():
        raise ImportError("missing backend")

    monkeypatch.setattr(router_agent, "get_reasoning_model", _raise_build_error)
    monkeypatch.setattr(router_agent, "get_chat_model", _raise_build_error)
    monkeypatch.setattr(router_agent, "classify_agent_class", lambda _q: "general")

    decision = router_agent.decide_route("test", use_reasoning=True)
    assert decision.route == "vector"
    assert decision.skill == "answer_with_citations"
    assert "router_invoke_error" in decision.reason


def test_router_web_route_is_downgraded_to_local_first(monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content='{"route":"web","reason":"freshness","skill":"web_fact_check"}')

    monkeypatch.setattr(router_agent, "get_reasoning_model", lambda: FakeModel())
    monkeypatch.setattr(router_agent, "get_chat_model", lambda: FakeModel())
    monkeypatch.setattr(router_agent, "classify_agent_class", lambda _q: "general")

    decision = router_agent.decide_route("最新漏洞")
    assert decision.route == "vector"
    assert "web_downgraded_to_local_first" in decision.reason


def test_router_smalltalk_stays_local_without_model(monkeypatch):
    class ShouldNotCallModel:
        def invoke(self, _messages):
            raise AssertionError("model should not be called for smalltalk")

    monkeypatch.setattr(router_agent, "get_reasoning_model", lambda: ShouldNotCallModel())
    monkeypatch.setattr(router_agent, "get_chat_model", lambda: ShouldNotCallModel())
    monkeypatch.setattr(router_agent, "classify_agent_class", lambda _q: "general")
    monkeypatch.setattr(router_agent, "is_smalltalk_query", lambda _q: True)

    decision = router_agent.decide_route("hi")
    assert decision.route == "vector"
    assert "smalltalk_local_only" in decision.reason


def test_router_respects_forced_agent_class_hint(monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content='{"route":"vector","reason":"ok","skill":"answer_with_citations"}')

    monkeypatch.setattr(router_agent, "get_reasoning_model", lambda: FakeModel())
    monkeypatch.setattr(router_agent, "get_chat_model", lambda: FakeModel())
    monkeypatch.setattr(router_agent, "classify_agent_class", lambda _q: "general")

    decision = router_agent.decide_route("hello", agent_class_hint="cybersecurity")
    assert decision.agent_class == "cybersecurity"
    assert "forced_agent_class=cybersecurity" in decision.reason


def test_synthesize_answer_returns_fallback_on_error(monkeypatch):
    class BrokenModel:
        def invoke(self, _messages):
            raise RuntimeError("boom")

    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda: BrokenModel())
    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda: BrokenModel())

    answer = synthesis_agent.synthesize_answer("q", "answer_with_citations", use_reasoning=True)
    assert answer == synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE


def test_synthesize_answer_returns_fallback_when_model_build_fails(monkeypatch):
    def _raise_build_error():
        raise ImportError("missing backend")

    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", _raise_build_error)
    monkeypatch.setattr(synthesis_agent, "get_chat_model", _raise_build_error)

    answer = synthesis_agent.synthesize_answer("q", "answer_with_citations", use_reasoning=True)
    assert answer == synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE


def test_stream_synthesize_yields_fallback_on_error(monkeypatch):
    class BrokenModel:
        def stream(self, _messages):
            raise RuntimeError("boom")

    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda: BrokenModel())
    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda: BrokenModel())

    chunks = list(synthesis_agent.stream_synthesize_answer("q", "answer_with_citations", use_reasoning=True))
    assert chunks == [synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE]


def test_stream_synthesize_yields_fallback_when_model_build_fails(monkeypatch):
    def _raise_build_error():
        raise ImportError("missing backend")

    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", _raise_build_error)
    monkeypatch.setattr(synthesis_agent, "get_chat_model", _raise_build_error)

    chunks = list(synthesis_agent.stream_synthesize_answer("q", "answer_with_citations", use_reasoning=True))
    assert chunks == [synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE]


def test_vector_rag_handles_non_list_retrieval_sources(monkeypatch):
    hybrid_stub = types.ModuleType("app.retrievers.hybrid_retriever")
    hybrid_stub.hybrid_search_with_diagnostics = lambda _q, allowed_sources=None: (
        [
            {
                "text": "chunk",
                "metadata": {"source": "s1"},
                "retrieval_sources": "vector",
            }
        ],
        {"rewrites": ["q"]},
    )
    sys.modules["app.retrievers.hybrid_retriever"] = hybrid_stub

    vector_agent = importlib.import_module("app.agents.vector_rag_agent")
    vector_agent = importlib.reload(vector_agent)
    monkeypatch.setattr(vector_agent, "get_settings", lambda: types.SimpleNamespace(max_context_chunks=2))

    result = vector_agent.run_vector_rag("q")
    assert result["retrieved_count"] == 1
    assert result["effective_hit_count"] == 1
    assert result["retrieval_diagnostics"]["rewrites"] == ["q"]
    assert result["citations"][0]["metadata"]["retrieval_sources"] == ["vector"]
    assert "[RETRIEVAL: vector]" in result["context"]


def test_stream_prefers_effective_hit_count_for_web_fallback(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")
    fake_synthesis_agent.stream_synthesize_answer = lambda **kwargs: iter(["ok"])
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "ok"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q: {"retrieved_count": 5, "effective_hit_count": 0, "context": "", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": True, "citations": [{"source": "web", "content": "x", "metadata": {}}], "context": "web ctx"}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("test", use_web_fallback=True, use_reasoning=True))
    web_events = [e for e in events if e.get("type") == "web_result"]
    assert web_events
    assert web_events[0].get("used") is True


def test_stream_does_not_use_web_when_fallback_enabled_and_local_evidence_sufficient(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")
    fake_synthesis_agent.stream_synthesize_answer = lambda **kwargs: iter(["ok"])
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "ok"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q, **_kwargs: {"retrieved_count": 3, "effective_hit_count": 3, "context": "local", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    web_calls = {"n": 0}

    def _web(_q):
        web_calls["n"] += 1
        return {"used": True, "citations": [{"source": "web", "content": "x", "metadata": {}}], "context": "web ctx"}

    fake_web_agent.run_web_research = _web

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("test", use_web_fallback=True, use_reasoning=True))
    assert [e for e in events if e.get("type") == "done"]
    assert [e for e in events if e.get("type") == "web_result"] == []
    assert web_calls["n"] == 0


def test_stream_emits_thought_events(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")
    fake_synthesis_agent.stream_synthesize_answer = lambda **kwargs: iter(["ok"])
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "ok"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q: {"retrieved_count": 3, "context": "", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": False, "citations": [], "context": ""}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("test", use_web_fallback=True, use_reasoning=True))
    thought_events = [e for e in events if e.get("type") == "thought"]
    assert len(thought_events) >= 2
    assert any("路由结果" in e.get("content", "") for e in thought_events)


def test_stream_continues_when_vector_retrieval_fails(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")
    fake_synthesis_agent.stream_synthesize_answer = lambda **kwargs: iter(["ok"])
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "ok"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")

    def _raise_vector(_q):
        raise RuntimeError("vector down")

    fake_vector_agent.run_vector_rag = _raise_vector
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": False, "citations": [], "context": ""}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("test", use_web_fallback=True, use_reasoning=True))
    thought_events = [e for e in events if e.get("type") == "thought"]
    done_events = [e for e in events if e.get("type") == "done"]
    assert done_events
    assert any("向量检索异常" in e.get("content", "") for e in thought_events)


def test_stream_forces_web_when_user_explicitly_requests_online_search(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")
    fake_synthesis_agent.stream_synthesize_answer = lambda **kwargs: iter(["ok"])
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "ok"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q: {"retrieved_count": 5, "context": "", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": True, "citations": [{"source": "web", "content": "x", "metadata": {}}], "context": "web ctx"}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("请上网查一下最新漏洞动态", use_web_fallback=True, use_reasoning=True))
    web_events = [e for e in events if e.get("type") == "web_result"]
    assert web_events
    assert web_events[0].get("used") is True


def test_stream_skips_web_for_casual_chat(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")
    fake_synthesis_agent.stream_synthesize_answer = lambda **kwargs: iter(["ok"])
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "ok"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q: {"retrieved_count": 0, "context": "", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": True, "citations": [{"source": "web", "content": "x", "metadata": {}}], "context": "web ctx"}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)
    monkeypatch.setattr(graph_streaming, "is_casual_chat_query", lambda _q: True)

    events = list(graph_streaming.run_query_stream("你是谁", use_web_fallback=True, use_reasoning=True))
    vector_events = [e for e in events if e.get("type") == "vector_result"]
    web_events = [e for e in events if e.get("type") == "web_result"]
    done_events = [e for e in events if e.get("type") == "done"]
    assert not vector_events
    assert not web_events
    assert done_events
    result = done_events[0].get("result", {})
    assert result.get("vector_result", {}).get("citations", []) == []
    assert result.get("web_result", {}).get("citations", []) == []


def test_synthesize_uses_high_temperature_for_casual_chat(monkeypatch):
    seen: dict[str, list[float | None]] = {"temps": []}

    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content="ok")

    def _fake_chat_model(temperature=None):
        seen["temps"].append(temperature)
        return FakeModel()

    monkeypatch.setattr(synthesis_agent, "get_chat_model", _fake_chat_model)
    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", _fake_chat_model)
    monkeypatch.setattr(synthesis_agent, "is_casual_chat_query", lambda _q: True)

    out = synthesis_agent.synthesize_answer("你是谁", "answer_with_citations", use_reasoning=False)
    assert out == "ok"
    assert synthesis_agent.CASUAL_CHAT_HIGH_TEMPERATURE in seen["temps"]


def test_local_evidence_model_does_not_expose_memory_context():
    model = LocalEvidenceChatModel()
    prompt = (
        "技能: answer_with_citations\n\n"
        "用户问题:\nhi\n\n"
        "记忆上下文:\n"
        "Short-term memory (latest rounds):\n[Round 1]\nQ: hi\nA: internal prior answer\n\n"
        "向量检索上下文:\n无\n\n"
        "图谱上下文:\n无\n\n"
        "联网补充上下文:\n无\n"
    )

    result = model.invoke([("system", synthesis_agent.ANSWER_PROMPT), ("human", prompt)])

    assert "Short-term memory" not in result.content
    assert "internal prior answer" not in result.content
    assert "当前本地知识库没有检索到足够证据" in result.content


def test_synthesize_refine_stops_after_max_5_rounds(monkeypatch):
    counters = {"review_calls": 0}

    class FakeModel:
        def invoke(self, messages):
            system_prompt = str(messages[0][1])
            if "答案质检与修订器" in system_prompt:
                counters["review_calls"] += 1
                idx = counters["review_calls"]
                return types.SimpleNamespace(
                    content=f'{{"is_correct": false, "issues": ["x"], "improved_answer": "ans-{idx}", "analysis": "rev"}}'
                )
            return types.SimpleNamespace(content="ans-0")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "is_casual_chat_query", lambda _q: False)

    out = synthesis_agent.synthesize_answer("q", "answer_with_citations", use_reasoning=False)
    assert out == "ans-5"
    assert counters["review_calls"] == 5


def test_synthesize_refine_stops_when_answer_is_similar(monkeypatch):
    counters = {"review_calls": 0}

    class FakeModel:
        def invoke(self, messages):
            system_prompt = str(messages[0][1])
            if "答案质检与修订器" in system_prompt:
                counters["review_calls"] += 1
                return types.SimpleNamespace(
                    content='{"is_correct": false, "issues": ["minor"], "improved_answer": "same answer", "analysis": "minor"}'
                )
            return types.SimpleNamespace(content="same answer")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "is_casual_chat_query", lambda _q: False)

    out = synthesis_agent.synthesize_answer("q", "answer_with_citations", use_reasoning=False)
    assert out == "same answer"
    assert counters["review_calls"] == 1


def test_stream_recovers_when_stream_synthesis_raises(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")

    def _boom_stream(**kwargs):
        raise RuntimeError("stream boom")
        yield "never"

    fake_synthesis_agent.stream_synthesize_answer = _boom_stream
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "fallback answer"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q: {"retrieved_count": 3, "context": "", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": False, "citations": [], "context": ""}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("test", use_web_fallback=True, use_reasoning=True))
    done_events = [e for e in events if e.get("type") == "done"]
    answer_chunks = [e for e in events if e.get("type") == "answer_chunk"]
    assert done_events
    assert answer_chunks
    assert answer_chunks[-1].get("content") == "fallback answer"


def test_stream_partial_then_error_emits_answer_reset(monkeypatch):
    fake_graph_agent = types.ModuleType("app.agents.graph_rag_agent")
    fake_graph_agent.run_graph_rag = lambda _q: {"entities": [], "context": "", "neighbors": []}
    fake_router_agent = types.ModuleType("app.agents.router_agent")
    fake_router_agent.decide_route = lambda _q, use_reasoning=True: types.SimpleNamespace(
        route="vector", reason="test", skill="answer_with_citations", agent_class="general"
    )
    fake_synthesis_agent = types.ModuleType("app.agents.synthesis_agent")

    def _broken_stream(**kwargs):
        yield "partial "
        raise RuntimeError("stream broken")

    fake_synthesis_agent.stream_synthesize_answer = _broken_stream
    fake_synthesis_agent.synthesize_answer = lambda **kwargs: "fallback final"
    fake_vector_agent = types.ModuleType("app.agents.vector_rag_agent")
    fake_vector_agent.run_vector_rag = lambda _q: {"retrieved_count": 1, "context": "", "citations": []}
    fake_web_agent = types.ModuleType("app.agents.web_research_agent")
    fake_web_agent.run_web_research = lambda _q: {"used": False, "citations": [], "context": ""}

    monkeypatch.setitem(sys.modules, "app.agents.graph_rag_agent", fake_graph_agent)
    monkeypatch.setitem(sys.modules, "app.agents.router_agent", fake_router_agent)
    monkeypatch.setitem(sys.modules, "app.agents.synthesis_agent", fake_synthesis_agent)
    monkeypatch.setitem(sys.modules, "app.agents.vector_rag_agent", fake_vector_agent)
    monkeypatch.setitem(sys.modules, "app.agents.web_research_agent", fake_web_agent)

    graph_streaming = importlib.import_module("app.graph.streaming")
    graph_streaming = importlib.reload(graph_streaming)

    events = list(graph_streaming.run_query_stream("test", use_web_fallback=True, use_reasoning=True))
    reset_events = [e for e in events if e.get("type") == "answer_reset"]
    done_events = [e for e in events if e.get("type") == "done"]
    assert reset_events
    assert reset_events[-1].get("content") == "fallback final"
    assert done_events
    assert done_events[-1].get("result", {}).get("answer") == "fallback final"
