"""Path-boundary regressions for evaluation administration routes."""

from fastapi.testclient import TestClient

from app.api.main import app


ADMIN = {
    "X-Test-User": "evaluation-admin",
    "X-Test-User-Id": "evaluation-admin",
    "X-Test-Role": "admin",
}


def test_evaluation_query_file_cannot_escape_data_directory():
    response = TestClient(app).get(
        "/api/evaluation/queries",
        params={"query_file": "../../pyproject.toml"},
        headers=ADMIN,
    )

    assert response.status_code == 400


def test_evaluation_result_id_rejects_path_like_values():
    response = TestClient(app).get(
        "/api/evaluation/results/%2E%2E%5Csecret",
        headers=ADMIN,
    )

    assert response.status_code in {400, 404}
