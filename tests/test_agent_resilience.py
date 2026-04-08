import importlib
import sys
import types

import app.agents.router_agent as router_agent
import app.agents.synthesis_agent as synthesis_agent


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

    decision = router_agent.decide_route("hi")
    assert decision.route == "vector"
    assert "smalltalk_local_only" in decision.reason


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
    hybrid_stub.hybrid_search = lambda _q: [
        {
            "text": "chunk",
            "metadata": {"source": "s1"},
            "retrieval_sources": "vector",
        }
    ]
    sys.modules["app.retrievers.hybrid_retriever"] = hybrid_stub

    vector_agent = importlib.import_module("app.agents.vector_rag_agent")
    vector_agent = importlib.reload(vector_agent)
    monkeypatch.setattr(vector_agent, "get_settings", lambda: types.SimpleNamespace(max_context_chunks=2))

    result = vector_agent.run_vector_rag("q")
    assert result["retrieved_count"] == 1
    assert result["citations"][0]["metadata"]["retrieval_sources"] == ["vector"]
    assert "[RETRIEVAL: vector]" in result["context"]


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
