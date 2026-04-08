import hashlib
import hmac
import secrets
import sqlite3
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


def _validate_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value not in {"admin", "analyst", "viewer"}:
        raise ValueError("unsupported role")
    return value


def _validate_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value not in {"active", "disabled"}:
        raise ValueError("unsupported status")
    return value


class AuthDBService:
    def __init__(self, db_path: Path | None = None, token_ttl_hours: int | None = None):
        settings = get_settings()
        self.db_path = db_path or settings.app_db_path
        self.token_ttl_hours = token_ttl_hours or settings.auth_token_ttl_hours
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  user_id TEXT PRIMARY KEY,
                  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                  salt TEXT NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT NOT NULL DEFAULT 'viewer',
                  status TEXT NOT NULL DEFAULT 'active',
                  created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_users_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                  token TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  username TEXT NOT NULL,
                  issued_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                  event_id TEXT PRIMARY KEY,
                  actor_user_id TEXT,
                  actor_role TEXT,
                  action TEXT NOT NULL,
                  resource_type TEXT NOT NULL,
                  resource_id TEXT,
                  result TEXT NOT NULL,
                  ip TEXT,
                  user_agent TEXT,
                  detail TEXT,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)")

    def _ensure_users_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(users)").fetchall()
        existing = {str(r["name"]) for r in rows}
        if "role" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'viewer'")
        if "status" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

    def register(self, username: str, password: str) -> dict[str, Any]:
        username = _validate_username(username)
        password = _validate_password(password)
        user_id = uuid.uuid4().hex
        salt_hex = secrets.token_hex(16)
        password_hash = _hash_password(password, salt_hex)
        now = _iso(_now())
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users(user_id, username, salt, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, username, salt_hex, password_hash, "viewer", "active", now),
                )
        except sqlite3.IntegrityError:
            raise ValueError("username already exists")
        return {"user_id": user_id, "username": username, "role": "viewer", "status": "active"}

    def login(self, username: str, password: str) -> dict[str, Any]:
        username = _validate_username(username)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, username, salt, password_hash, role, status FROM users WHERE lower(username)=lower(?)",
                (username,),
            ).fetchone()
            if row is None:
                raise ValueError("invalid credentials")
            if str(row["status"]).lower() != "active":
                raise ValueError("user disabled")
            hashed = _hash_password(password or "", str(row["salt"]))
            if not hmac.compare_digest(hashed, str(row["password_hash"])):
                raise ValueError("invalid credentials")

            token = secrets.token_urlsafe(40)
            issued_at = _now()
            expires_at = issued_at + timedelta(hours=self.token_ttl_hours)
            conn.execute(
                "INSERT INTO auth_sessions(token, user_id, username, issued_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (token, str(row["user_id"]), str(row["username"]), _iso(issued_at), _iso(expires_at)),
            )
            return {
                "token": token,
                "token_type": "bearer",
                "expires_at": _iso(expires_at),
                "user": {
                    "user_id": str(row["user_id"]),
                    "username": str(row["username"]),
                    "role": str(row["role"]),
                    "status": str(row["status"]),
                },
            }

    def logout(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            now = _now()
            row = conn.execute(
                """
                SELECT s.user_id AS user_id, s.username AS username, s.expires_at AS expires_at,
                       u.role AS role, u.status AS status
                FROM auth_sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.token=?
                """,
                (token,),
            ).fetchone()
            if row is None:
                return None
            if _parse_iso(str(row["expires_at"])) <= now:
                conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
                return None
            if str(row["status"]).lower() != "active":
                conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
                return None
            return {
                "user_id": str(row["user_id"]),
                "username": str(row["username"]),
                "role": str(row["role"]),
                "status": str(row["status"]),
            }

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, username, role, status, created_at FROM users ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_user_role(self, user_id: str, role: str) -> dict[str, Any] | None:
        role = _validate_role(role)
        with self._connect() as conn:
            result = conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
            if result.rowcount <= 0:
                return None
            row = conn.execute("SELECT user_id, username, role, status, created_at FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def update_user_status(self, user_id: str, status: str) -> dict[str, Any] | None:
        status = _validate_status(status)
        with self._connect() as conn:
            result = conn.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
            if result.rowcount <= 0:
                return None
            if status == "disabled":
                conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
            row = conn.execute("SELECT user_id, username, role, status, created_at FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def add_audit_log(
        self,
        action: str,
        resource_type: str,
        result: str,
        actor_user_id: str | None = None,
        actor_role: str | None = None,
        resource_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        detail: str | None = None,
    ) -> dict[str, Any]:
        event_id = uuid.uuid4().hex
        created_at = _iso(_now())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs(event_id, actor_user_id, actor_role, action, resource_type, resource_id, result, ip, user_agent, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, actor_user_id, actor_role, action, resource_type, resource_id, result, ip, user_agent, detail, created_at),
            )
        return {
            "event_id": event_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "ip": ip,
            "user_agent": user_agent,
            "detail": detail,
            "created_at": created_at,
        }

    def list_audit_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        cap = max(1, min(limit, 1000))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_id, actor_user_id, actor_role, action, resource_type, resource_id, result, ip, user_agent, detail, created_at
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (cap,),
            ).fetchall()
            return [dict(r) for r in rows]
