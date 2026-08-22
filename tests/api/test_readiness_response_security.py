import json

from app.api.routes.operations import health


def test_ready_response_does_not_expose_internal_paths_hosts_or_errors(monkeypatch):
    monkeypatch.setattr(health.query_guard, "stats", lambda: {"inflight": 0, "waiting": 0})
    monkeypatch.setattr(health.shadow_queue, "stats", lambda: {"queue_size": 0, "workers": 0})
    monkeypatch.setattr(
        health,
        "_check_ollama_ready",
        lambda: {
            "ok": False,
            "required": False,
            "latency_ms": 1,
            "path": "http://internal-model:11434/api/tags",
            "models": ["private-model"],
            "error": "connection failed at C:\\secret\\runtime",
        },
    )
    monkeypatch.setattr(
        health,
        "_check_chroma_ready",
        lambda: {
            "ok": True,
            "required": True,
            "latency_ms": 1,
            "path": "C:\\secret\\chroma",
        },
    )
    monkeypatch.setattr(
        health,
        "_check_redis_ready",
        lambda: {
            "ok": True,
            "required": False,
            "latency_ms": 1,
            "host": "redis.internal:6379",
        },
    )
    monkeypatch.setattr(health, "_check_postgres_ready", lambda: {"ok": True, "required": False, "latency_ms": 1})
    monkeypatch.setattr(health, "_check_openai_api_ready", lambda: {"ok": True, "required": False, "latency_ms": 1})
    monkeypatch.setattr(health, "_check_anthropic_api_ready", lambda: {"ok": True, "required": False, "latency_ms": 1})
    monkeypatch.setattr(health, "_check_neo4j_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})
    monkeypatch.setattr(health, "_check_embedding_model_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})

    response = health.ready()
    payload = json.loads(response.body)
    serialized = json.dumps(payload)

    assert "internal-model" not in serialized
    assert "private-model" not in serialized
    assert "secret" not in serialized
    assert "redis.internal" not in serialized
    assert payload["services"]["ollama"]["error"] == "dependency check failed"
