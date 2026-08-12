"""Focused ownership regression for the public query stream."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import query_request, query_stream
from app.main import app
from app.pipeline.profiles import PipelineProfile


def _execution_events(response_text: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response_text.splitlines()
        if line.startswith("data: ")
    ]


def test_regular_stream_is_executed_by_stream_module_and_preserves_progressive_content(monkeypatch) -> None:
    """Delegating execution back to the request module drops the owned stream seam."""
    calls: list[tuple[object, str]] = []

    class OwnedPipeline:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def execute_stream(self, pipeline_request, *, execution_id: str):
            calls.append((pipeline_request, execution_id))
            yield {"type": "answer_chunk", "content": "partial answer"}
            yield {
                "type": "done",
                "result": {
                    "answer": "complete answer",
                    "route": "vector",
                    "execution_id": execution_id,
                    "vector_result": {"citations": []},
                    "graph_result": {"entities": []},
                    "web_result": {"used": False, "citations": []},
                    "detected_language": "en",
                },
            }

    class DelegatedPipeline:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def execute_stream(self, *_args: object, **_kwargs: object):
            raise AssertionError("stream execution must not live in query_request")
            yield

    monkeypatch.setattr(query_stream, "RAGPipeline", OwnedPipeline, raising=False)
    monkeypatch.setattr(query_request, "RAGPipeline", DelegatedPipeline, raising=False)

    token = uuid4().hex
    response = TestClient(app).post(
        "/api/query/stream",
        data={"question": f"Explain stream ownership {token}", "request_id": token},
        headers={
            "X-Test-User": f"stream-owner-{token}",
            "X-Test-Role": "viewer",
            "X-Test-User-Id": f"stream-owner-{token}",
        },
    )

    assert response.status_code == 200
    events = _execution_events(response.text)
    progressive_event = next(event for event in events if event["stage"] == "synthesize")
    assert {item["key"]: item["value"] for item in progressive_event["metadata"]}["content"] == "partial answer"
    assert any(event["stage"] == "complete" for event in events)
    assert len(calls) == 1
    pipeline_request, execution_id = calls[0]
    assert pipeline_request.profile is PipelineProfile.STANDARD
    assert pipeline_request.question.startswith("Explain stream ownership")
    assert execution_id
