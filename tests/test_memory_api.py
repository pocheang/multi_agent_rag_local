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
