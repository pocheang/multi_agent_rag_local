import pytest
from datetime import datetime, timezone

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

api_main = pytest.importorskip("app.api.main")


def test_admin_ops_overview_requires_admin():
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_viewer",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.get("/admin/ops/overview")
        assert res.status_code == 403
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_ops_overview_returns_metrics(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        api_main.auth_service,
        "list_audit_logs",
        lambda limit=1000: [
            {
                "event_id": "1",
                "actor_user_id": "u_admin",
                "actor_role": "admin",
                "action": "query.run",
                "resource_type": "query",
                "resource_id": "s1",
                "result": "success",
                "created_at": now_iso,
            },
            {
                "event_id": "2",
                "actor_user_id": "u_admin",
                "actor_role": "admin",
                "action": "auth.login",
                "resource_type": "auth",
                "resource_id": None,
                "result": "failed",
                "created_at": now_iso,
            },
        ],
    )
    monkeypatch.setattr(
        api_main.auth_service,
        "list_users",
        lambda: [
            {"user_id": "u_admin", "username": "admin", "role": "admin", "status": "active"},
            {"user_id": "u_a", "username": "a", "role": "analyst", "status": "disabled"},
        ],
    )
    monkeypatch.setattr(api_main.auth_service, "count_active_sessions", lambda: 3)
    monkeypatch.setattr(api_main, "_check_ollama_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})
    monkeypatch.setattr(api_main, "_check_neo4j_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})
    monkeypatch.setattr(api_main, "_check_chroma_ready", lambda: {"ok": True, "required": True, "latency_ms": 1})

    try:
        res = client.get("/admin/ops/overview?hours=48&actor_user_id=u_admin&action_keyword=query")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["window_hours"] == 48
        assert data["kpi"]["requests_total"] >= 0
        assert "services" in data
        assert "top_actions" in data
        assert "top_error_reasons" in data
        assert "slow_requests" in data
        assert data["filters"]["actor_user_id"] == "u_admin"
        assert data["filters"]["action_keyword"] == "query"
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_ops_export_csv_returns_csv(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(
        api_main.auth_service,
        "list_audit_logs",
        lambda limit=1000: [
            {
                "event_id": "1",
                "actor_user_id": "u_admin",
                "actor_role": "admin",
                "action": "query.run",
                "resource_type": "query",
                "resource_id": "s1",
                "result": "success",
                "detail": "ok",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    try:
        res = client.get("/admin/ops/export.csv?hours=24")
        assert res.status_code == 200
        assert "text/csv" in (res.headers.get("content-type", ""))
        assert "request_count" in res.text
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_audit_logs_supports_filters(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    captured: dict[str, object] = {}

    def _fake_list(limit=200, actor_user_id=None, action_keyword=None, event_category=None, severity=None, result=None):
        captured["limit"] = limit
        captured["actor_user_id"] = actor_user_id
        captured["action_keyword"] = action_keyword
        captured["event_category"] = event_category
        captured["severity"] = severity
        captured["result"] = result
        return [
            {
                "event_id": "evt1",
                "actor_user_id": "u_admin",
                "actor_role": "admin",
                "action": "admin.user.status_update",
                "event_category": "admin",
                "severity": "info",
                "resource_type": "user",
                "resource_id": "u1",
                "result": "success",
                "detail": "ok",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    monkeypatch.setattr(api_main.auth_service, "list_audit_logs", _fake_list)
    try:
        res = client.get(
            "/admin/audit-logs?limit=50&actor_user_id=u_admin&action_keyword=admin.user&event_category=admin&severity=info&result=success"
        )
        assert res.status_code == 200
        assert captured["limit"] == 50
        assert captured["actor_user_id"] == "u_admin"
        assert captured["action_keyword"] == "admin.user"
        assert captured["event_category"] == "admin"
        assert captured["severity"] == "info"
        assert captured["result"] == "success"
        assert len(res.json()) == 1
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_ops_retrieval_profile_and_canary(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    try:
        get_res = client.get("/admin/ops/retrieval-profile")
        assert get_res.status_code == 200
        assert "active_profile" in get_res.json()

        set_res = client.post("/admin/ops/retrieval-profile", json={"profile": "baseline"})
        assert set_res.status_code == 200
        assert set_res.json()["active_profile"] == "baseline"

        canary_res = client.post(
            "/admin/ops/canary",
            json={"enabled": True, "baseline_percent": 20, "safe_percent": 10, "seed": "qa"},
        )
        assert canary_res.status_code == 200
        assert canary_res.json()["canary"]["enabled"] is True
        assert canary_res.json()["canary"]["baseline_percent"] == 20
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_ops_rollback_and_trends(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(api_main, "read_benchmark_trends", lambda limit=30: [{"created_at": "2026-04-09T00:00:00+00:00"}])
    try:
        rollback_res = client.post("/admin/ops/rollback")
        assert rollback_res.status_code == 200
        assert rollback_res.json()["ok"] is True
        assert rollback_res.json()["state"]["active_profile"] == "baseline"

        trends_res = client.get("/admin/ops/benchmark/trends?limit=5")
        assert trends_res.status_code == 200
        assert trends_res.json()["count"] == 1
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_ops_benchmark_run(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(api_main, "_load_benchmark_queries", lambda path, limit=100: ["q1", "q2"])
    monkeypatch.setattr(
        api_main,
        "run_query",
        lambda *args, **kwargs: {
            "grounding": {"support_ratio": 0.8},
            "vector_result": {"citations": [{"source": "a", "content": "b"}]},
            "web_result": {"citations": []},
        },
    )
    saved: list[dict] = []
    monkeypatch.setattr(api_main, "append_benchmark_trend", lambda x: saved.append(x))
    try:
        res = client.post("/admin/ops/benchmark/run?max_queries=2&strategy=advanced")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["result"]["num_queries"] == 2
        assert len(saved) == 1
    finally:
        api_main.app.dependency_overrides.clear()
