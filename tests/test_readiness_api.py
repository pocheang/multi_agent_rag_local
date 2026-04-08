import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

api_main = pytest.importorskip("app.api.main")


def test_ready_returns_ok_when_dependencies_ok(monkeypatch):
    monkeypatch.setattr(api_main, "_check_ollama_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})
    monkeypatch.setattr(api_main, "_check_neo4j_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})
    monkeypatch.setattr(api_main, "_check_chroma_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})

    client = TestClient(api_main.app)
    res = client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["blocking_failures"] == []


def test_ready_returns_503_when_required_dependency_fails(monkeypatch):
    monkeypatch.setattr(api_main, "_check_ollama_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})
    monkeypatch.setattr(api_main, "_check_neo4j_ready", lambda: {"ok": False, "required": True, "latency_ms": 1, "error": "down"})
    monkeypatch.setattr(api_main, "_check_chroma_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})

    client = TestClient(api_main.app)
    res = client.get("/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "degraded"
    assert "neo4j" in data["blocking_failures"]
