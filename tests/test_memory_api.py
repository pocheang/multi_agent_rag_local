import uuid
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

api_main = pytest.importorskip("app.api.main")
from app.services.history import HistoryStore
from app.services.memory_store import MemoryStore


@pytest.fixture
def memory_api_env(monkeypatch):
    root = Path("tests/.tmp") / f"memory-api-{uuid.uuid4().hex[:8]}"
    history_store = HistoryStore(base_dir=root / "sessions")
    memory_store = MemoryStore(base_dir=root / "long_memory")
    user = {"user_id": "u-test", "username": "tester", "role": "viewer", "status": "active"}

    monkeypatch.setattr(api_main, "_history_store_for_user", lambda _user: history_store)
    monkeypatch.setattr(api_main, "_memory_store_for_user", lambda _user: memory_store)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "normalize_and_validate_user_question", lambda text: (text or "").strip())
    monkeypatch.setattr(api_main, "normalize_user_question", lambda text: (text or "").strip())
    monkeypatch.setattr(api_main, "enhance_user_question_for_completion", lambda text: (text or "").strip())
    monkeypatch.setattr(api_main, "is_casual_chat_query", lambda _text: False)
    monkeypatch.setattr(api_main, "classify_agent_class", lambda _text: "general")

    api_main.app.dependency_overrides[api_main._require_user] = lambda: user
    client = TestClient(api_main.app)
    try:
        yield client, user, history_store, memory_store
    finally:
        api_main.app.dependency_overrides.clear()


def test_long_memory_list_and_delete(memory_api_env):
    client, _user, _history_store, memory_store = memory_api_env
    session_id = "session-memory-api"
    candidate = memory_store.add_candidate(
        session_id=session_id,
        question="how to isolate host quickly",
        answer="isolate the endpoint from network, preserve memory and collect logs immediately.",
        signals={"vector_retrieved": 3, "citation_count": 4, "web_used": False, "route": "vector", "reason": "ok"},
    )
    assert candidate is not None

    res = client.get(f"/sessions/{session_id}/memories/long")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["candidate_id"] == candidate["candidate_id"]

    deleted = client.delete(f"/sessions/{session_id}/memories/long/{candidate['candidate_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["memory_id"] == candidate["candidate_id"]

    after = client.get(f"/sessions/{session_id}/memories/long")
    assert after.status_code == 200
    assert after.json() == []


def test_query_injects_memory_context_and_promotes(memory_api_env, monkeypatch):
    client, _user, history_store, memory_store = memory_api_env
    session_id = "session-query-memory"
    for i in range(1, 5):
        history_store.append_message(session_id, "user", f"q{i}")
        history_store.append_message(session_id, "assistant", f"a{i} with enough context for memory capture")
    memory_store.add_candidate(
        session_id=session_id,
        question="sql injection defense",
        answer="use parameterized statements and strict input validation on all DB paths.",
        signals={"vector_retrieved": 3, "citation_count": 4, "web_used": False, "route": "vector", "reason": "ok"},
    )
    before_count = len(memory_store.get_session_payload(session_id)["candidates"])
    seen: dict[str, str] = {}

    def fake_run_query(question: str, use_web_fallback: bool = True, use_reasoning: bool = True, memory_context: str = ""):
        seen["question"] = question
        seen["memory_context"] = memory_context
        return {
            "answer": "Prioritize parameterized queries, WAF signatures, and suspicious payload monitoring.",
            "route": "vector",
            "reason": "ok",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "vector_result": {"retrieved_count": 3, "citations": [{"source": "s1", "content": "c1", "metadata": {}}]},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": ["t1"],
        }

    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": "how to prevent sql injection",
            "use_web_fallback": True,
            "use_reasoning": True,
            "session_id": session_id,
        },
    )
    assert res.status_code == 200
    assert "Short-term memory" in seen["memory_context"]
    assert "q2" in seen["memory_context"]
    assert "q1" not in seen["memory_context"]
    assert "Long-term memory" in seen["memory_context"]
    assert "sql injection" in seen["memory_context"]
    after_count = len(memory_store.get_session_payload(session_id)["candidates"])
    assert after_count == before_count + 1


def test_query_does_not_inject_memory_for_smalltalk(memory_api_env, monkeypatch):
    client, _user, history_store, memory_store = memory_api_env
    session_id = "session-query-smalltalk-memory"
    history_store.append_message(session_id, "user", "previous q")
    history_store.append_message(session_id, "assistant", "previous a with enough context for memory capture")
    memory_store.add_candidate(
        session_id=session_id,
        question="private incident detail",
        answer="sensitive internal context should not appear in smalltalk.",
        signals={"vector_retrieved": 2, "citation_count": 2, "web_used": False, "route": "vector", "reason": "ok"},
    )
    seen: dict[str, str] = {}

    def fake_run_query(question: str, use_web_fallback: bool = True, use_reasoning: bool = True, memory_context: str = ""):
        seen["question"] = question
        seen["memory_context"] = memory_context
        return {
            "answer": "你好，我在。",
            "route": "smalltalk_fast",
            "reason": "smalltalk_fast_path",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "vector_result": {"retrieved_count": 0, "citations": []},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": [],
        }

    monkeypatch.setattr(api_main, "is_casual_chat_query", lambda _text: True)
    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": "hi",
            "use_web_fallback": True,
            "use_reasoning": True,
            "session_id": session_id,
        },
    )
    assert res.status_code == 200
    assert seen["question"] == "hi"
    assert seen["memory_context"] == ""


def test_stream_query_injects_memory_context_and_promotes(memory_api_env, monkeypatch):
    client, _user, history_store, memory_store = memory_api_env
    session_id = "session-stream-memory"
    history_store.append_message(session_id, "user", "previous question")
    history_store.append_message(session_id, "assistant", "previous answer with enough details for history context")
    memory_store.add_candidate(
        session_id=session_id,
        question="incident response process",
        answer="containment first, then forensics collection, then eradication and recovery.",
        signals={"vector_retrieved": 2, "citation_count": 3, "web_used": False, "route": "vector", "reason": "ok"},
    )
    before_count = len(memory_store.get_session_payload(session_id)["candidates"])
    seen: dict[str, str] = {}

    def fake_run_query_stream(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
    ):
        seen["question"] = question
        seen["memory_context"] = memory_context
        yield {"type": "status", "message": "synthesizing"}
        yield {
            "type": "done",
            "result": {
                "answer": "Contain first, preserve evidence, then eradicate root cause and recover services safely.",
                "route": "vector",
                "reason": "ok",
                "skill": "answer_with_citations",
                "agent_class": "general",
                "vector_result": {"retrieved_count": 2, "citations": [{"source": "s1", "content": "c1", "metadata": {}}]},
                "graph_result": {"entities": []},
                "web_result": {"used": False, "citations": [], "context": ""},
                "thoughts": ["t1"],
            },
        }

    monkeypatch.setattr(api_main, "run_query_stream", fake_run_query_stream)
    res = client.post(
        "/query/stream",
        data={
            "question": "incident response checklist",
            "use_web_fallback": "true",
            "use_reasoning": "true",
            "session_id": session_id,
        },
    )
    assert res.status_code == 200
    assert "\"type\": \"done\"" in res.text
    assert "Long-term memory" in seen["memory_context"]
    after_count = len(memory_store.get_session_payload(session_id)["candidates"])
    assert after_count == before_count + 1


def test_stream_query_does_not_inject_memory_for_smalltalk(memory_api_env, monkeypatch):
    client, _user, history_store, memory_store = memory_api_env
    session_id = "session-stream-smalltalk-memory"
    history_store.append_message(session_id, "user", "previous question")
    history_store.append_message(session_id, "assistant", "previous answer with enough details for history context")
    memory_store.add_candidate(
        session_id=session_id,
        question="private incident detail",
        answer="sensitive internal context should not appear in smalltalk.",
        signals={"vector_retrieved": 2, "citation_count": 2, "web_used": False, "route": "vector", "reason": "ok"},
    )
    seen: dict[str, str] = {}

    def fake_run_query_stream(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
    ):
        seen["question"] = question
        seen["memory_context"] = memory_context
        yield {
            "type": "done",
            "result": {
                "answer": "你好，我在。",
                "route": "smalltalk_fast",
                "reason": "smalltalk_fast_path",
                "skill": "answer_with_citations",
                "agent_class": "general",
                "vector_result": {"retrieved_count": 0, "citations": []},
                "graph_result": {"entities": []},
                "web_result": {"used": False, "citations": [], "context": ""},
                "thoughts": [],
            },
        }

    monkeypatch.setattr(api_main, "is_casual_chat_query", lambda _text: True)
    monkeypatch.setattr(api_main, "run_query_stream", fake_run_query_stream)
    res = client.post(
        "/query/stream",
        data={
            "question": "hi",
            "use_web_fallback": "true",
            "use_reasoning": "true",
            "session_id": session_id,
        },
    )
    assert res.status_code == 200
    assert "\"type\": \"done\"" in res.text
    assert seen["question"] == "hi"
    assert seen["memory_context"] == ""


def test_query_passes_agent_class_hint_to_workflow(memory_api_env, monkeypatch):
    client, _user, _history_store, _memory_store = memory_api_env
    seen: dict[str, str] = {}

    def fake_run_query(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
        allowed_sources: list[str] | None = None,
        agent_class_hint: str | None = None,
    ):
        seen["question"] = question
        seen["agent_class_hint"] = str(agent_class_hint or "")
        return {
            "answer": "ok",
            "route": "vector",
            "reason": "ok",
            "skill": "answer_with_citations",
            "agent_class": "cybersecurity",
            "vector_result": {"retrieved_count": 1, "citations": []},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": [],
        }

    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": "hello",
            "use_web_fallback": True,
            "use_reasoning": True,
            "agent_class_hint": "cybersecurity",
        },
    )
    assert res.status_code == 200
    assert seen["question"] == "hello"
    assert seen["agent_class_hint"] == "cybersecurity"


def test_query_applies_question_enhancement_before_workflow(memory_api_env, monkeypatch):
    client, _user, _history_store, _memory_store = memory_api_env
    seen: dict[str, str] = {}

    monkeypatch.setattr(api_main, "enhance_user_question_for_completion", lambda text: f"{text}\n[enhanced]")

    def fake_run_query(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
        allowed_sources: list[str] | None = None,
        agent_class_hint: str | None = None,
    ):
        seen["question"] = question
        return {
            "answer": "ok",
            "route": "vector",
            "reason": "ok",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "vector_result": {"retrieved_count": 1, "citations": []},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": [],
        }

    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": "这个怎么修",
            "use_web_fallback": True,
            "use_reasoning": True,
        },
    )
    assert res.status_code == 200
    assert "[enhanced]" in seen["question"]


def test_stream_query_applies_question_enhancement_before_workflow(memory_api_env, monkeypatch):
    client, _user, _history_store, _memory_store = memory_api_env
    seen: dict[str, str] = {}

    monkeypatch.setattr(api_main, "enhance_user_question_for_completion", lambda text: f"{text}\n[enhanced]")

    def fake_run_query_stream(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
    ):
        seen["question"] = question
        yield {"type": "done", "result": {"answer": "ok", "vector_result": {}, "graph_result": {}, "web_result": {"used": False, "citations": []}}}

    monkeypatch.setattr(api_main, "run_query_stream", fake_run_query_stream)
    res = client.post(
        "/query/stream",
        data={
            "question": "那个怎么做",
            "use_web_fallback": "true",
            "use_reasoning": "true",
        },
    )
    assert res.status_code == 200
    assert "[enhanced]" in seen["question"]


def test_stream_query_returns_error_event_on_unexpected_failure(memory_api_env, monkeypatch):
    client, _user, _history_store, _memory_store = memory_api_env

    def fake_run_query_stream(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
    ):
        yield {"type": "status", "message": "routing"}
        raise RuntimeError("boom in stream")

    monkeypatch.setattr(api_main, "run_query_stream", fake_run_query_stream)
    res = client.post(
        "/query/stream",
        data={
            "question": "请总结这个文档",
            "use_web_fallback": "true",
            "use_reasoning": "true",
        },
    )
    assert res.status_code == 200
    assert '"type": "error"' in res.text
    assert '"error": "internal_error"' in res.text


def test_query_skips_question_enhancement_for_casual_chat(memory_api_env, monkeypatch):
    client, _user, _history_store, _memory_store = memory_api_env
    seen: dict[str, str] = {}

    monkeypatch.setattr(api_main, "is_casual_chat_query", lambda _text: True)
    monkeypatch.setattr(api_main, "enhance_user_question_for_completion", lambda text: f"{text}\n[enhanced]")

    def fake_run_query(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
        allowed_sources: list[str] | None = None,
        agent_class_hint: str | None = None,
    ):
        seen["question"] = question
        return {
            "answer": "ok",
            "route": "vector",
            "reason": "ok",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "vector_result": {"retrieved_count": 0, "citations": []},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": [],
        }

    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": "你好，你在干嘛呢",
            "use_web_fallback": True,
            "use_reasoning": True,
        },
    )
    assert res.status_code == 200
    assert "[enhanced]" not in seen["question"]


def test_query_clears_local_citations_when_allowed_sources_empty(memory_api_env, monkeypatch):
    client, _user, _history_store, _memory_store = memory_api_env
    monkeypatch.setattr(api_main, "_allowed_sources_for_user", lambda _u: [])
    monkeypatch.setattr(api_main, "synthesize_answer", lambda **_kwargs: "scoped answer")

    def fake_run_query(
        question: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
        allowed_sources: list[str] | None = None,
        agent_class_hint: str | None = None,
    ):
        return {
            "answer": "scoped answer",
            "route": "vector",
            "reason": "ok",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "vector_result": {
                "retrieved_count": 2,
                "effective_hit_count": 2,
                "citations": [
                    {"source": "s1", "content": "c1", "metadata": {"source": "secret-a.md"}},
                    {"source": "s2", "content": "c2", "metadata": {"source": "secret-b.md"}},
                ],
            },
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": [],
        }

    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": "scope fallback check",
            "use_web_fallback": False,
            "use_reasoning": False,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["citations"] == []
    assert int((body.get("debug") or {}).get("vector_retrieved", -1)) == 0
    assert (body.get("debug") or {}).get("source_scope", {}).get("answer_resynthesized") is True


def test_source_scope_rebuilds_vector_context_from_allowed_citations(monkeypatch):
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    result = {
        "answer": "answer",
        "vector_result": {
            "context": "secret context should be removed",
            "retrieved_count": 2,
            "effective_hit_count": 2,
            "citations": [
                {"source": "allowed.md", "content": "allowed text", "metadata": {"source": "allowed.md", "retrieval_sources": ["vector"]}},
                {"source": "secret.md", "content": "secret text", "metadata": {"source": "secret.md", "retrieval_sources": ["vector"]}},
            ],
        },
    }

    scoped = api_main._enforce_result_source_scope(
        result,
        allowed_sources=["allowed.md"],
        request=object(),
        user={"user_id": "u-test", "role": "viewer"},
    )

    vector = scoped["vector_result"]
    assert vector["retrieved_count"] == 1
    assert vector["effective_hit_count"] == 1
    assert "allowed text" in vector["context"]
    assert "secret" not in vector["context"]
    assert scoped["source_scope"]["filtered_vector_citations"] == 1


def test_source_scope_clears_graph_when_no_allowed_sources(monkeypatch):
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    result = {
        "answer": "answer",
        "vector_result": {"context": "", "citations": [], "retrieved_count": 0},
        "graph_result": {
            "context": "secret graph",
            "entities": ["secret"],
            "neighbors": [{"entity": "secret"}],
            "paths": [{"source": "secret"}],
        },
    }

    scoped = api_main._enforce_result_source_scope(
        result,
        allowed_sources=[],
        request=object(),
        user={"user_id": "u-test", "role": "viewer"},
    )

    assert scoped["graph_result"]["context"] == ""
    assert scoped["graph_result"]["entities"] == []
    assert scoped["graph_result"]["neighbors"] == []
    assert scoped["source_scope"]["filtered_graph"] is True


def test_resynthesize_after_source_scope_uses_filtered_context(monkeypatch):
    seen: dict[str, str] = {}

    def fake_synthesize_answer(**kwargs):
        seen["vector_context"] = kwargs.get("vector_context", "")
        return "answer from allowed context"

    monkeypatch.setattr(api_main, "synthesize_answer", fake_synthesize_answer)
    result = {
        "answer": "old answer with secret",
        "skill": "answer_with_citations",
        "source_scope": {"filtered_vector_citations": 1},
        "vector_result": {"context": "allowed only"},
        "graph_result": {"context": ""},
        "web_result": {"context": ""},
    }

    out = api_main._resynthesize_after_source_scope(
        result,
        question="q",
        memory_context="m",
        use_reasoning=False,
    )

    assert out["answer"] == "answer from allowed context"
    assert seen["vector_context"] == "allowed only"
    assert out["source_scope"]["answer_resynthesized"] is True


def test_query_cache_key_changes_when_visible_index_changes(monkeypatch):
    user = {"user_id": "u-test", "role": "viewer"}
    rows = [{"source": "a.md", "chunks": 1, "visibility": "private", "owner_user_id": "u-test", "agent_class": "general"}]
    monkeypatch.setattr(api_main, "_list_visible_documents_for_user", lambda _user: rows)
    monkeypatch.setattr(api_main, "_source_mtime_ns", lambda _source: 0)

    first = api_main._query_cache_key(
        user=user,
        session_id=None,
        question="same",
        use_web_fallback=False,
        use_reasoning=False,
        retrieval_strategy=None,
        agent_class_hint=None,
        request_id=None,
        mode="query",
    )
    rows[0]["chunks"] = 2
    second = api_main._query_cache_key(
        user=user,
        session_id=None,
        question="same",
        use_web_fallback=False,
        use_reasoning=False,
        retrieval_strategy=None,
        agent_class_hint=None,
        request_id=None,
        mode="query",
    )

    assert first != second


def test_query_discards_invalid_cache_payload_and_recomputes(memory_api_env, monkeypatch):
    client, user, _history_store, _memory_store = memory_api_env
    question = f"cache-guard-{uuid.uuid4().hex[:8]}"
    cache_key = api_main._query_cache_key(
        user=user,
        session_id=None,
        question=question,
        use_web_fallback=False,
        use_reasoning=False,
        retrieval_strategy=None,
        agent_class_hint=None,
        request_id=None,
        mode="query",
    )
    # Poisoned payload shape, similar to old stream payload format.
    api_main.query_result_cache.set(cache_key, {"result": {"answer": "bad", "route": "vector"}}, session_id=None)

    calls = {"n": 0}

    def fake_run_query(
        query_text: str,
        use_web_fallback: bool = True,
        use_reasoning: bool = True,
        memory_context: str = "",
        allowed_sources: list[str] | None = None,
        agent_class_hint: str | None = None,
    ):
        calls["n"] += 1
        return {
            "answer": f"fresh:{query_text}",
            "route": "vector",
            "reason": "ok",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "vector_result": {"retrieved_count": 0, "effective_hit_count": 0, "citations": []},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": [], "context": ""},
            "thoughts": [],
        }

    monkeypatch.setattr(api_main, "run_query", fake_run_query)
    res = client.post(
        "/query",
        json={
            "question": question,
            "use_web_fallback": False,
            "use_reasoning": False,
        },
    )
    assert res.status_code == 200
    assert calls["n"] == 1
    assert str(res.json().get("answer", "")).startswith("fresh:")
