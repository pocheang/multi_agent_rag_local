import uuid
from pathlib import Path

import pytest

from app.services.auth import AuthService


def _mk(prefix: str) -> Path:
    path = Path("tests/.tmp") / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_register_and_login_success():
    root = _mk("auth")
    service = AuthService(users_path=root / "users.json", sessions_path=root / "sessions.json", token_ttl_hours=1)

    user = service.register("alice", "Password123")
    assert user["username"] == "alice"
    login = service.login("alice", "Password123")
    assert login["token"]
    me = service.get_user_by_token(login["token"])
    assert me is not None
    assert me["username"] == "alice"


def test_register_duplicate_username_fails():
    root = _mk("auth-dupe")
    service = AuthService(users_path=root / "users.json", sessions_path=root / "sessions.json", token_ttl_hours=1)
    service.register("bob", "Password123")
    with pytest.raises(ValueError):
        service.register("bob", "Password123")


def test_login_invalid_password_fails():
    root = _mk("auth-bad-pass")
    service = AuthService(users_path=root / "users.json", sessions_path=root / "sessions.json", token_ttl_hours=1)
    service.register("charlie", "Password123")
    with pytest.raises(ValueError):
        service.login("charlie", "wrong-pass")
