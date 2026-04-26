import pytest

from app.services.rate_limiter import SlidingWindowLimiter

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

api_main = pytest.importorskip("app.api.main")


def test_sliding_window_limiter_block_and_reset():
    limiter = SlidingWindowLimiter(max_attempts=2, window_seconds=300)
    key = "k"
    assert limiter.is_limited(key) is False
    limiter.record(key)
    assert limiter.is_limited(key) is False
    limiter.record(key)
    assert limiter.is_limited(key) is True
    limiter.reset(key)
    assert limiter.is_limited(key) is False


def test_login_rate_limit_blocks_repeated_failures(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "login_limiter", SlidingWindowLimiter(max_attempts=2, window_seconds=300))

    def _fail_login(_username: str, _password: str):
        raise ValueError("invalid credentials")

    monkeypatch.setattr(api_main.auth_service, "login", _fail_login)

    payload = {"username": "tester01", "password": "Password1"}
    res1 = client.post("/auth/login", json=payload)
    res2 = client.post("/auth/login", json=payload)
    res3 = client.post("/auth/login", json=payload)
    assert res1.status_code == 401
    assert res2.status_code == 401
    assert res3.status_code == 429


def test_register_rate_limit_blocks_repeated_failures(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "register_limiter", SlidingWindowLimiter(max_attempts=2, window_seconds=300))

    def _fail_register(_username: str, _password: str):
        raise ValueError("username already exists")

    monkeypatch.setattr(api_main.auth_service, "register", _fail_register)

    payload = {"username": "tester01", "password": "Password1"}
    res1 = client.post("/auth/register", json=payload)
    res2 = client.post("/auth/register", json=payload)
    res3 = client.post("/auth/register", json=payload)
    assert res1.status_code == 400
    assert res2.status_code == 400
    assert res3.status_code == 429


def test_admin_page_requires_admin_permission(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u1",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.get("/admin")
        assert res.status_code == 403
    finally:
        api_main.app.dependency_overrides.clear()


def test_upload_rejects_too_many_files(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main.settings, "upload_max_files", 1)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u2",
        "username": "analyst",
        "role": "analyst",
        "status": "active",
    }
    try:
        files = [
            ("files", ("a.md", b"hello", "text/markdown")),
            ("files", ("b.md", b"world", "text/markdown")),
        ]
        res = client.post("/upload", files=files)
        assert res.status_code == 400
        assert "too many files" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_query_rejects_nonexistent_session_id(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u3",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.post(
            "/query",
            json={"question": "hello", "session_id": "session-not-found"},
        )
        assert res.status_code == 404
        assert "session not found" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_stream_query_rejects_invalid_session_id_format(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u4",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.post(
            "/query/stream",
            data={"question": "hello", "session_id": "../escape"},
        )
        assert res.status_code == 400
        assert "invalid session_id format" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_get_session_rejects_invalid_session_id_format(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u5",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.get("/sessions/bad.id")
        assert res.status_code == 400
        assert "invalid session_id format" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_list_long_term_memories_rejects_invalid_session_id_format(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u6",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.get("/sessions/bad.id/memories/long")
        assert res.status_code == 400
        assert "invalid session_id format" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_cookie_auth_blocks_cross_origin_mutation(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_by_token",
        lambda _token: {
            "user_id": "u7",
            "username": "viewer",
            "role": "viewer",
            "status": "active",
        },
    )
    monkeypatch.setattr(api_main.auth_service, "touch_session", lambda _token: None)

    res = client.post(
        "/auth/logout",
        cookies={str(api_main.settings.auth_cookie_name): "tok_cookie"},
        headers={"Origin": "http://evil.example"},
    )
    assert res.status_code == 403
    assert "csrf validation failed" in (res.json().get("detail", "") or "")


def test_cookie_auth_allows_same_origin_mutation(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_by_token",
        lambda _token: {
            "user_id": "u8",
            "username": "viewer",
            "role": "viewer",
            "status": "active",
        },
    )
    monkeypatch.setattr(api_main.auth_service, "touch_session", lambda _token: None)
    monkeypatch.setattr(api_main.auth_service, "logout", lambda _token: None)

    origin = api_main.settings.cors_origins[0] if api_main.settings.cors_origins else "http://localhost:5173"
    res = client.post(
        "/auth/logout",
        cookies={str(api_main.settings.auth_cookie_name): "tok_cookie"},
        headers={"Origin": origin},
    )
    assert res.status_code == 200
    assert res.json().get("ok") is True


def test_query_rejects_runtime_private_base_url_in_user_settings(monkeypatch):
    client = TestClient(api_main.app)
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u9",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_metadata",
        lambda _user_id, key: (
            {
                "provider": "custom",
                "api_key": "sk-custom-x",
                "base_url": "http://127.0.0.1:9000/v1",
                "model": "custom-model",
                "temperature": 0.7,
                "max_tokens": 512,
            }
            if key == "api_settings"
            else None
        ),
    )
    try:
        res = client.post(
            "/query",
            json={"question": "hello", "use_web_fallback": False, "use_reasoning": False},
        )
        assert res.status_code == 400
        assert "invalid api settings" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()
