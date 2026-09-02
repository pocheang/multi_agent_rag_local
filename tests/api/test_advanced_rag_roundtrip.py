"""End-to-end wiring check for the chat round trip.

Exercises the real handler against a real HistoryStore with only the pipeline
stubbed, so it covers what the unit tests cannot: that a query actually lands in
the session store and that the next turn's memory context picks it back up.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.api.routes.public import query as advanced_rag
from app.pipeline.contracts import PipelineResult, PipelineRoute
from app.services.sessions.history import HistoryStore


class _StubPipeline:
    """Stands in for RAGPipeline; records the request it was handed."""

    seen: list[Any] = []

    async def execute(self, request):
        type(self).seen.append(request)
        return PipelineResult(
            answer=f"answer to: {request.question}",
            route=PipelineRoute(route="vector", reason="stub"),
            execution_metadata={"validation": {"state": "validated"}},
        )


class _Request:
    """Minimal stand-in for starlette Request; only used by audit helpers."""

    client = None
    headers: dict[str, str] = {}
    url = type("U", (), {"path": "/api/advanced-rag/query"})()


@pytest.fixture
def history(monkeypatch) -> HistoryStore:
    # Deliberately not pytest's tmp_path: its basetemp root needs directory
    # permissions that are not available on every Windows checkout.
    root = Path(tempfile.mkdtemp(prefix="querymind-history-"))
    store = HistoryStore(base_dir=root / "sessions")
    monkeypatch.setattr(advanced_rag, "_history_store_for_user", lambda user: store)
    monkeypatch.setattr(advanced_rag, "_promote_long_term_memory", lambda **_: None)
    monkeypatch.setattr(advanced_rag, "_require_permission", lambda *a, **k: None)
    monkeypatch.setattr(advanced_rag, "_resolve_advanced_allowed_sources", lambda user, req: ["corpus"])
    monkeypatch.setattr(advanced_rag, "RAGPipeline", _StubPipeline)
    _StubPipeline.seen = []
    try:
        yield store
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.asyncio
async def test_two_turns_persist_and_carry_context(history, monkeypatch):
    user = {"user_id": "u1", "username": "u", "role": "user", "permissions": []}
    session = history.create_session()
    session_id = session["session_id"]

    monkeypatch.setattr(
        advanced_rag,
        "_build_memory_context_for_session",
        lambda u, sid, q: "\n".join(
            f"{m['role']}: {m['content']}" for m in (history.get_session(sid) or {}).get("messages", [])
        ),
    )

    first = await advanced_rag._process_advanced_rag_query_impl(
        advanced_rag.AdvancedRAGRequest(query="What is RAG?", session_id=session_id), _Request(), user
    )
    second = await advanced_rag._process_advanced_rag_query_impl(
        advanced_rag.AdvancedRAGRequest(query="And its downsides?", session_id=session_id), _Request(), user
    )

    # 1. Both turns of both exchanges are persisted, in order.
    messages = history.get_session(session_id)["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "What is RAG?"
    assert messages[2]["content"] == "And its downsides?"

    # 2. The second call carried the first exchange into the pipeline.
    second_request = _StubPipeline.seen[1]
    assert second_request.session_id == session_id
    assert second_request.conversation, "second turn must carry conversation context"
    assert "What is RAG?" in second_request.conversation[0].content

    # 3. execution_id reaches the client on every turn.
    assert first.metadata["execution_id"]
    assert second.metadata["execution_id"]
    assert first.metadata["execution_id"] != second.metadata["execution_id"]


@pytest.mark.asyncio
async def test_query_without_session_id_persists_nothing(history):
    user = {"user_id": "u1", "username": "u", "role": "user", "permissions": []}
    session_id = history.create_session()["session_id"]

    await advanced_rag._process_advanced_rag_query_impl(
        advanced_rag.AdvancedRAGRequest(query="stateless"), _Request(), user
    )

    assert history.get_session(session_id)["messages"] == []
