"""Security regressions for the registered session-management API."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient


def _headers(user_id: str) -> dict[str, str]:
    return {
        "X-Test-User": user_id,
        "X-Test-User-Id": user_id,
        "X-Test-Role": "viewer",
        "X-CSRF-Token": "a" * 32,
    }


def test_session_metadata_requires_authentication():
    from app.api.main import app

    session_id = uuid.uuid4().hex
    response = TestClient(app).post(
        f"/api/v1/sessions/{session_id}/metadata",
        headers={"X-CSRF-Token": "a" * 32},
        json={"tags": ["private"]},
    )

    assert response.status_code == 401


def test_session_metadata_is_isolated_between_users():
    from app.api.main import app

    client = TestClient(app)
    session_id = uuid.uuid4().hex
    owner_headers = _headers("metadata-owner")
    other_headers = _headers("metadata-other")

    created = client.post(
        f"/api/v1/sessions/{session_id}/metadata",
        headers=owner_headers,
        json={"tags": ["owner-only"]},
    )
    leaked = client.get(
        f"/api/v1/sessions/{session_id}/metadata",
        headers=other_headers,
    )

    assert created.status_code == 200
    assert leaked.status_code == 404

    client.delete(f"/api/v1/sessions/{session_id}/metadata", headers=owner_headers)


def test_session_export_requires_authentication():
    from app.api.main import app

    session_id = uuid.uuid4().hex
    response = TestClient(app).post(
        f"/api/v1/sessions/{session_id}/export",
        headers={"X-CSRF-Token": "a" * 32},
        json={"format": "json"},
    )

    assert response.status_code == 401


def test_session_export_reads_the_authenticated_users_real_history():
    from app.api.dependencies import _history_store_for_user
    from app.api.main import app
    from app.services.sessions.service import get_metadata_service

    user_id = "session-export-owner"
    user = {"user_id": user_id}
    session_id = uuid.uuid4().hex
    history = _history_store_for_user(user)
    history.create_session(session_id=session_id)
    history.append_message(session_id, "user", "private question")
    metadata = get_metadata_service(user_id)
    metadata.create_metadata(session_id, tags=["private"])

    response = TestClient(app).post(
        f"/api/v1/sessions/{session_id}/export",
        headers=_headers(user_id),
        json={"format": "json", "include_context": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["messages"][0]["content"] == "private question"

    history.delete_session(session_id)
    metadata.delete_metadata(session_id)


def test_session_import_persists_history_and_metadata_for_authenticated_user():
    from app.api.dependencies import _history_store_for_user
    from app.api.main import app
    from app.services.sessions.service import get_metadata_service

    user_id = "session-import-owner"
    session_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    payload = {
        "session_id": session_id,
        "metadata": {
            "session_id": session_id,
            "tags": ["imported"],
            "category": "research",
            "description": "import test",
            "auto_tags": [],
            "created_at": now,
            "updated_at": now,
            "query_count": 0,
            "last_query_at": None,
        },
        "messages": [{"role": "user", "content": "imported question", "metadata": {}}],
        "context": None,
        "export_version": "1.0",
        "exported_at": now,
    }

    response = TestClient(app).post(
        "/api/v1/sessions/import",
        headers=_headers(user_id),
        files={"file": ("session.json", __import__("json").dumps(payload), "application/json")},
        data={"conflict_strategy": "skip"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    assert _history_store_for_user({"user_id": user_id}).get_session(session_id)["messages"][0]["content"] == "imported question"
    assert get_metadata_service(user_id).get_metadata(session_id).tags == ["imported"]

    _history_store_for_user({"user_id": user_id}).delete_session(session_id)
    get_metadata_service(user_id).delete_metadata(session_id)


def test_session_import_rejects_invalid_metadata_before_creating_history():
    import json

    from app.api.dependencies import _history_store_for_user
    from app.api.main import app

    user_id = "session-import-invalid-owner"
    session_id = f"invalid-import-{uuid.uuid4().hex}"
    payload = {
        "export_version": "1.0",
        "session_id": session_id,
        "messages": [{"role": "user", "content": "must not persist"}],
        "metadata": {"tags": ["invalid tag"]},
    }

    response = TestClient(app).post(
        "/api/v1/sessions/import",
        headers=_headers(user_id),
        files={"file": ("session.json", json.dumps(payload), "application/json")},
    )

    assert response.status_code == 400
    assert _history_store_for_user({"user_id": user_id}).get_session(session_id) is None
