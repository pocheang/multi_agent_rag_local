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
