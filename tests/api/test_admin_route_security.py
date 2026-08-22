"""Security regression tests for standalone admin/diagnostic routers."""

from fastapi.testclient import TestClient

from app.api.main import app


def test_agent_quality_admin_routes_require_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/agent-quality/stats")

    assert response.status_code == 401


def test_web_activity_admin_routes_require_authentication():
    with TestClient(app) as client:
        for path in (
            "/api/v1/admin/web-activity/logs",
            "/api/v1/admin/web-activity/top-users",
            "/api/v1/admin/web-activity/export",
        ):
            response = client.get(path)
            assert response.status_code == 401, path


def test_agent_diagnostic_data_requires_authentication():
    with TestClient(app) as client:
        for path in (
            "/api/v1/agents/status",
            "/api/v1/agents/config",
            "/api/v1/agents/trace/not-found",
        ):
            response = client.get(path)
            assert response.status_code == 401, path
