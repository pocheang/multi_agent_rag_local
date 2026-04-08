import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _hash_password(password: str, salt_hex: str, iterations: int = 200_000) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def _validate_username(username: str) -> str:
    value = (username or "").strip()
    if len(value) < 3 or len(value) > 32:
        raise ValueError("username length must be 3-32")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if any(ch not in allowed for ch in value):
        raise ValueError("username contains unsupported characters")
    return value


def _validate_password(password: str) -> str:
    value = password or ""
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    if not any(ch.islower() for ch in value):
        raise ValueError("password must include lowercase letters")
    if not any(ch.isupper() for ch in value):
        raise ValueError("password must include uppercase letters")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("password must include digits")
    return value


class AuthService:
    def __init__(self, users_path: Path | None = None, sessions_path: Path | None = None, token_ttl_hours: int | None = None):
        settings = get_settings()
        self.users_path = users_path or settings.users_path
        self.sessions_path = sessions_path or settings.auth_sessions_path
        self.token_ttl_hours = token_ttl_hours or settings.auth_token_ttl_hours
        self.users_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def register(self, username: str, password: str) -> dict[str, Any]:
        username = _validate_username(username)
        password = _validate_password(password)
        data = self._read_json(self.users_path, {"users": {}})
        users = data.setdefault("users", {})
        key = username.lower()
        if key in users:
            raise ValueError("username already exists")

        salt_hex = secrets.token_hex(16)
        users[key] = {
            "user_id": uuid.uuid4().hex,
            "username": username,
            "salt": salt_hex,
            "password_hash": _hash_password(password, salt_hex),
            "created_at": _iso(_now()),
        }
        self._write_json(self.users_path, data)
        return {"user_id": users[key]["user_id"], "username": username}

    def login(self, username: str, password: str) -> dict[str, Any]:
        username = _validate_username(username)
        data = self._read_json(self.users_path, {"users": {}})
        users = data.get("users", {})
        row = users.get(username.lower())
        if not row:
            raise ValueError("invalid credentials")
        hashed = _hash_password(password or "", row["salt"])
        if not hmac.compare_digest(hashed, row["password_hash"]):
            raise ValueError("invalid credentials")

        token = secrets.token_urlsafe(40)
        expires_at = _now() + timedelta(hours=self.token_ttl_hours)
        sessions = self._read_json(self.sessions_path, {"sessions": {}})
        sessions.setdefault("sessions", {})[token] = {
            "user_id": row["user_id"],
            "username": row["username"],
            "issued_at": _iso(_now()),
            "expires_at": _iso(expires_at),
        }
        self._write_json(self.sessions_path, sessions)
        return {"token": token, "token_type": "bearer", "expires_at": _iso(expires_at), "user": {"user_id": row["user_id"], "username": row["username"]}}

    def logout(self, token: str) -> None:
        sessions = self._read_json(self.sessions_path, {"sessions": {}})
        payload = sessions.get("sessions", {})
        if token in payload:
            payload.pop(token, None)
            self._write_json(self.sessions_path, sessions)

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        sessions = self._read_json(self.sessions_path, {"sessions": {}})
        payload = sessions.get("sessions", {})
        self._cleanup_expired(payload)
        row = payload.get(token)
        if row is None:
            self._write_json(self.sessions_path, sessions)
            return None
        self._write_json(self.sessions_path, sessions)
        return {"user_id": row["user_id"], "username": row["username"]}

    def _cleanup_expired(self, payload: dict[str, Any]) -> None:
        now = _now()
        expired = [token for token, row in payload.items() if _parse_iso(row.get("expires_at", _iso(now))) <= now]
        for token in expired:
            payload.pop(token, None)
