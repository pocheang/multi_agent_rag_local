import types

import app.agents.rag.vector as vector_agent
import app.agents.router.routing as router_agent
import app.agents.synthesizer.generation as synthesis_agent
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
    monkeypatch.setattr(router_agent, "ENABLE_WEB_ROUTE_DOWNGRADE", True)

    decision = router_agent.decide_route("最新漏洞", use_llm_intent=False)
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


def test_router_invalid_route_and_skill_fall_back_safely(monkeypatch):
    from app.agents.shared.cache import clear_agent_caches

    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(
                content='{"route":"unknown_route","reason":"bad_output","skill":"not_a_skill"}'
            )

    # Clear cache before test to ensure clean state
    clear_agent_caches()

    monkeypatch.setattr(router_agent, "get_reasoning_model", lambda: FakeModel())
    monkeypatch.setattr(router_agent, "get_chat_model", lambda: FakeModel())
    monkeypatch.setattr(router_agent, "classify_agent_class", lambda _q: "general")
    monkeypatch.setattr(router_agent, "is_smalltalk_query", lambda _q: False)

    decision = router_agent.decide_route("invalid route test", use_llm_intent=False)
    assert decision.route == "vector"
    assert decision.skill == "answer_with_citations"
    assert "invalid_route=unknown_route" in decision.reason
    assert "invalid_skill=not_a_skill" in decision.reason


def test_synthesize_answer_returns_fallback_on_error(monkeypatch):
    class BrokenModel:
        def invoke(self, _messages):
            raise RuntimeError("boom")

    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda: BrokenModel())
    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda: BrokenModel())

    result = synthesis_agent.synthesize_answer("q", "answer_with_citations", use_reasoning=True)
    assert isinstance(result, dict)
    assert result["answer"] == synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE


def test_synthesize_answer_returns_fallback_when_model_build_fails(monkeypatch):
    def _raise_build_error():
        raise ImportError("missing backend")

    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", _raise_build_error)
    monkeypatch.setattr(synthesis_agent, "get_chat_model", _raise_build_error)

    result = synthesis_agent.synthesize_answer("q", "answer_with_citations", use_reasoning=True)
    assert isinstance(result, dict)
    assert result["answer"] == synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE


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
    fake_hybrid_search = lambda _q, allowed_sources=None: (
        [
            {
                "text": "chunk",
                "metadata": {"source": "s1"},
                "retrieval_sources": "vector",
            }
        ],
        {"rewrites": ["q"]},
    )
    monkeypatch.setattr(vector_agent, "hybrid_search_with_diagnostics", fake_hybrid_search)
    monkeypatch.setattr(vector_agent, "get_settings", lambda: types.SimpleNamespace(max_context_chunks=2))

    result = vector_agent.run_vector_rag("q")
    assert result["retrieved_count"] == 1
    assert result["effective_hit_count"] == 1
    assert result["retrieval_diagnostics"]["rewrites"] == ["q"]
    assert result["citations"][0]["metadata"]["retrieval_sources"] == ["vector"]
    assert "[RETRIEVAL: vector]" in result["context"]








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

    result = synthesis_agent.synthesize_answer("你是谁", "answer_with_citations", use_reasoning=False)
    assert isinstance(result, dict)
    assert result["answer"] == "ok"
    assert 0.9 in seen["temps"]


def test_synthesize_strips_placeholder_citation_without_evidence(monkeypatch):
    """A no-evidence answer must not expose a model-invented marker."""
    received: list[tuple[str, str]] = []

    class FakeModel:
        def invoke(self, messages):
            received.extend(messages)
            return types.SimpleNamespace(content="Hello! [doc_id:page]")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    result = synthesis_agent.synthesize_answer(
        "hi",
        "answer_with_citations",
        enable_fact_verification=False,
    )

    assert all("[doc_id:page]" not in prompt for _role, prompt in received)
    assert result["answer"] == "Hello!"


def test_synthesize_non_casual_answer_strips_placeholder_citation_without_evidence(monkeypatch):
    """Citation-free prompts also protect no-evidence factual questions."""
    received: list[tuple[str, str]] = []

    class FakeModel:
        def invoke(self, messages):
            received.extend(messages)
            return types.SimpleNamespace(content="Hello! [doc_id:page]")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    result = synthesis_agent.synthesize_answer(
        "What is retrieval augmented generation?",
        "answer_with_citations",
        enable_fact_verification=False,
    )

    assert all("[doc_id:page]" not in prompt for _role, prompt in received)
    assert result["answer"] == "Hello!"


def test_synthesize_preserves_allowed_citation_and_strips_invented_marker(monkeypatch):
    """Only labels supplied by retrieved evidence may remain visible."""
    received: list[tuple[str, str]] = []

    class FakeModel:
        def invoke(self, messages):
            received.extend(messages)
            return types.SimpleNamespace(content="RAG uses retrieved evidence [guide:7] [fake:99].")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    result = synthesis_agent.synthesize_answer(
        "What is RAG?",
        "answer_with_citations",
        vector_context="[guide:7] RAG definition",
        enable_fact_verification=False,
    )

    assert any("[guide:7]" in prompt for _role, prompt in received)
    assert any("never invent" in prompt.lower() for _role, prompt in received)
    assert result["answer"] == "RAG uses retrieved evidence [guide:7]."


def test_stream_strict_quality_refines_with_evidence_labels(monkeypatch):
    """Strict-quality streaming must pass evidence labels to the review path."""

    class FakeModel:
        def stream(self, _messages):
            yield types.SimpleNamespace(content="RAG answer [guide:7].")

        def invoke(self, _messages):
            return types.SimpleNamespace(
                content=(
                    '{"is_correct": false, "issues": ["x"], '
                    '"improved_answer": "Reviewed RAG answer [guide:7].", "analysis": "x"}'
                )
            )

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda temperature=None: FakeModel())

    chunks = list(
        synthesis_agent.stream_synthesize_answer(
            "What is RAG?",
            "answer_with_citations",
            vector_context="[guide:7] RAG definition",
            profile="strict_quality",
        )
    )

    assert {"type": "reset", "content": "Reviewed RAG answer [guide:7]."} in chunks
    assert {"type": "metadata", "detected_language": "en"} in chunks
    assert synthesis_agent.SYNTHESIS_FALLBACK_MESSAGE not in chunks


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


def test_synthesize_strict_quality_refine_is_capped_at_one_round(monkeypatch):
    counters = {"review_calls": 0}

    class FakeModel:
        def invoke(self, messages):
            human_prompt = str(messages[1][1])
            if "当前答案:" in human_prompt:
                counters["review_calls"] += 1
                idx = counters["review_calls"]
                return types.SimpleNamespace(
                    content=f'{{"is_correct": false, "issues": ["x"], "improved_answer": "ans-{idx}", "analysis": "rev"}}'
                )
            return types.SimpleNamespace(content="ans-0")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "is_casual_chat_query", lambda _q: False)

    result = synthesis_agent.synthesize_answer(
        "q",
        "answer_with_citations",
        use_reasoning=False,
        enable_fact_verification=False,
        profile="strict_quality",
    )
    assert isinstance(result, dict)
    assert result["answer"] == "ans-1"
    assert counters["review_calls"] == 1


def test_synthesize_refine_stops_when_answer_is_similar(monkeypatch):
    counters = {"review_calls": 0}

    class FakeModel:
        def invoke(self, messages):
            human_prompt = str(messages[1][1])
            if "当前答案:" in human_prompt:
                counters["review_calls"] += 1
                return types.SimpleNamespace(
                    content='{"is_correct": false, "issues": ["minor"], "improved_answer": "same answer", "analysis": "minor"}'
                )
            return types.SimpleNamespace(content="same answer")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "get_reasoning_model", lambda temperature=None: FakeModel())
    monkeypatch.setattr(synthesis_agent, "is_casual_chat_query", lambda _q: False)

    result = synthesis_agent.synthesize_answer(
        "q",
        "answer_with_citations",
        use_reasoning=False,
        enable_fact_verification=False,
        profile="strict_quality",
    )
    assert isinstance(result, dict)
    assert result["answer"] == "same answer"
    assert counters["review_calls"] == 1
