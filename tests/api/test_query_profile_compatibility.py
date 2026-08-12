"""Public `/api/query` response contracts for compatibility profiles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import query_request, query_request_execution
from app.main import app
from app.pipeline.contracts import PipelineResult, PipelineRoute


class _QueryCache:
    """Minimal route-boundary cache fake; it never performs external I/O."""

    def __init__(self, get_response: Callable[[], dict[str, Any] | None], *, accepts_inflight: bool = True) -> None:
        self._get_response = get_response
        self._accepts_inflight = accepts_inflight

    def get(self, *_args: object, **_kwargs: object) -> dict[str, Any] | None:
        return self._get_response()

    def mark_inflight(self, *_args: object, **_kwargs: object) -> bool:
        return self._accepts_inflight

    def clear_inflight(self, *_args: object, **_kwargs: object) -> None:
        return None

    def set(self, *_args: object, **_kwargs: object) -> None:
        return None


@pytest.fixture
def user_headers() -> dict[str, str]:
    return {"X-Test-User": "profile-user", "X-Test-Role": "viewer", "X-Test-User-Id": "profile-user"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _assert_public_query_contract(payload: dict[str, Any], *, answer: str, route: str) -> None:
    """Catch a missing response-model field at the actual HTTP boundary."""
    assert {"answer", "citations", "route"}.issubset(payload)
    assert payload["answer"] == answer
    assert payload["route"] == route
    assert isinstance(payload["citations"], list)


def _cached_payload(*, answer: str, route: str) -> dict[str, Any]:
    return {
        "answer": answer,
        "citations": [{"source": "cache.md", "content": "Cached source", "metadata": {}}],
        "route": route,
        "graph_entities": [],
        "web_used": False,
        "detected_language": "en",
        "debug": {},
    }


def _pipeline_result(payload: dict[str, Any]) -> PipelineResult:
    """Keep API tests on the public pipeline boundary, not legacy workflow calls."""
    return PipelineResult(
        answer=str(payload["answer"]),
        citations=(),
        route=PipelineRoute(route=str(payload["route"])),
        execution_metadata={"compatibility_payload": payload},
    )


def _install_cache(monkeypatch: pytest.MonkeyPatch, cache: _QueryCache) -> None:
    """Keep cache-only tests at the production request boundary without Redis."""
    monkeypatch.setattr(query_request, "query_result_cache", cache)
    monkeypatch.setattr(query_request_execution, "query_result_cache", cache)
    monkeypatch.setattr(query_request, "_query_cache_key", lambda **_kwargs: "profile-contract-key")


def test_normal_query_endpoint_always_exposes_answer_citations_and_route(
    client: TestClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing a normal-profile response field breaks existing HTTP clients."""
    _install_cache(monkeypatch, _QueryCache(lambda: None))

    result = {
        "answer": "Normal profile answer.",
        "route": "vector",
        "reason": "test",
        "skill": "test",
        "agent_class": "general",
        "vector_result": {"citations": [], "retrieved_count": 0},
        "graph_result": {"entities": []},
        "web_result": {"used": False, "citations": []},
        "detected_language": "en",
    }
    with patch(
        "app.api.routes.query_request_execution.RAGPipeline.execute_sync",
        return_value=_pipeline_result(result),
    ):
        response = client.post("/api/query", json={"question": "What is RAG?"}, headers=user_headers)

    assert response.status_code == 200
    _assert_public_query_contract(response.json(), answer="Normal profile answer.", route="vector")


def test_inventory_early_return_endpoint_always_exposes_answer_citations_and_route(
    client: TestClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inventory early return must retain the normal public response shape."""
    monkeypatch.setattr(query_request, "_is_file_inventory_question", lambda _question: True)
    monkeypatch.setattr(query_request, "_build_user_file_inventory_answer", lambda _user: "You have two files.")

    response = client.post("/api/query", json={"question": "Which files do I have?"}, headers=user_headers)

    assert response.status_code == 200
    _assert_public_query_contract(response.json(), answer="You have two files.", route="policy")


def test_cached_query_endpoint_always_exposes_answer_citations_and_route(
    client: TestClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dropping a field while parsing a completed compatibility cache breaks clients."""
    _install_cache(monkeypatch, _QueryCache(lambda: _cached_payload(answer="Cached answer.", route="graph")))

    response = client.post("/api/query", json={"question": "Explain graph retrieval."}, headers=user_headers)

    assert response.status_code == 200
    _assert_public_query_contract(response.json(), answer="Cached answer.", route="graph")


def test_hot_cached_query_endpoint_always_exposes_answer_citations_and_route(
    client: TestClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The in-flight hot-cache handoff must preserve the public response shape."""
    responses = iter((None, _cached_payload(answer="Hot cached answer.", route="web")))
    _install_cache(monkeypatch, _QueryCache(lambda: next(responses), accepts_inflight=False))

    response = client.post("/api/query", json={"question": "Find current policy."}, headers=user_headers)

    assert response.status_code == 200
    _assert_public_query_contract(response.json(), answer="Hot cached answer.", route="web")
