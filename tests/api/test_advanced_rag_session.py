"""Regression tests: the advanced-rag endpoint must persist the exchange.

Before 2026-08-29 the chat path never wrote to the session history store and
never returned its tracker execution id, so conversations were lost on reload
and the SSE execution-trace endpoint could not be subscribed to.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes.compatibility import advanced_rag


class _FakeHistoryStore:
    def __init__(self) -> None:
        self.appended: list[tuple[str, str, str, dict[str, Any]]] = []

    def get_session(self, session_id: str) -> dict[str, Any]:
        return {"session_id": session_id, "messages": []}

    def append_message(
        self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.appended.append((session_id, role, content, metadata or {}))
        return {"session_id": session_id, "messages": []}


@pytest.mark.asyncio
async def test_query_persists_user_and_assistant_messages(monkeypatch):
    """A query carrying session_id must write exactly one user message and
    one assistant message into the session history store."""
    store = _FakeHistoryStore()
    monkeypatch.setattr(advanced_rag, "_history_store_for_user", lambda user: store)
    monkeypatch.setattr(advanced_rag, "_promote_long_term_memory", lambda **_: None)

    await advanced_rag._persist_exchange(
        user={"user_id": "u1"},
        session_id="s1",
        question="What is RAG?",
        answer="Retrieval-augmented generation. [E1]",
        metadata={"route": "vector"},
    )

    roles = [role for _sid, role, _content, _meta in store.appended]
    assert roles == ["user", "assistant"]
    assert store.appended[0][2] == "What is RAG?"
    assert store.appended[1][2] == "Retrieval-augmented generation. [E1]"
    assert store.appended[1][3]["route"] == "vector"


@pytest.mark.asyncio
async def test_persist_is_a_noop_without_session_id(monkeypatch):
    """Omitting session_id must keep today's stateless behaviour."""
    store = _FakeHistoryStore()
    monkeypatch.setattr(advanced_rag, "_history_store_for_user", lambda user: store)

    await advanced_rag._persist_exchange(user={"user_id": "u1"}, session_id=None, question="q", answer="a", metadata={})

    assert store.appended == []


@pytest.mark.asyncio
async def test_persistence_failure_never_propagates(monkeypatch):
    """The answer was already produced; a history write failure must not 500."""

    class _BrokenStore(_FakeHistoryStore):
        def append_message(self, *args: Any, **kwargs: Any):
            raise RuntimeError("disk full")

    monkeypatch.setattr(advanced_rag, "_history_store_for_user", lambda user: _BrokenStore())
    monkeypatch.setattr(advanced_rag, "_promote_long_term_memory", lambda **_: None)

    await advanced_rag._persist_exchange(user={"user_id": "u1"}, session_id="s1", question="q", answer="a", metadata={})


def test_execution_id_is_returned_in_metadata():
    """The tracker execution id must reach the client, otherwise the SSE
    execution-trace endpoint can never be subscribed to."""
    metadata = advanced_rag._response_metadata(
        pipeline_result_metadata={"validation": {"state": "validated"}},
        route="vector",
        citations=[{"source": "doc1"}],
        execution_id="exec-123",
        session_id="s1",
    )

    assert metadata["execution_id"] == "exec-123"
    assert metadata["session_id"] == "s1"
    assert metadata["route"] == "vector"
    assert metadata["citations"] == [{"source": "doc1"}]
    assert metadata["validation"] == {"state": "validated"}


def test_request_model_accepts_session_id():
    """session_id must be optional so existing callers keep working."""
    assert advanced_rag.AdvancedRAGRequest(query="q").session_id is None
    assert advanced_rag.AdvancedRAGRequest(query="q", session_id="s1").session_id == "s1"
