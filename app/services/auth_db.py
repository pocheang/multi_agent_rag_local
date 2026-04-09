import hashlib
import hmac
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.alerting import resolve_signing_secret, sign_payload


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


def _normalize_classification_value(value: str | None, max_len: int = 64) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > max_len:
        raise ValueError(f"classification field too long (max {max_len})")
    return text


def _classify_audit_event(action: str, result: str) -> tuple[str, str]:
    action_lc = (action or "").strip().lower()
    result_lc = (result or "").strip().lower()

    if action_lc.startswith("auth."):
        category = "auth"
    elif action_lc.startswith("query.") or action_lc.startswith("document."):
        category = "data"
    elif action_lc.startswith("admin."):
        category = "admin"
    elif action_lc.startswith("prompt."):
        category = "prompt"
    else:
        category = "system"

    if result_lc == "failed":
        severity = "high"
    elif result_lc == "denied":
        severity = "medium"
    else:
        severity = "info"
    return category, severity


class AuthDBService:
    def __init__(self, db_path: Path | None = None, token_ttl_hours: int | None = None):
        settings = get_settings()
        self.db_path = db_path or settings.app_db_path
        self.token_ttl_hours = token_ttl_hours or settings.auth_token_ttl_hours
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        settings = get_settings()
        timeout_s = max(1.0, float(getattr(settings, "sqlite_busy_timeout_seconds", 10) or 10))
        conn = sqlite3.connect(self.db_path, timeout=timeout_s)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {int(timeout_s * 1000)}")
        conn.execute("PRAGMA journal_mode=WAL")
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
                  created_by_user_id TEXT,
                  created_by_username TEXT,
                  admin_ticket_id TEXT,
                  admin_approval_token_hash TEXT,
                  business_unit TEXT,
                  department TEXT,
                  user_type TEXT,
                  data_scope TEXT,
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
                  last_seen_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                )
                """
            )
            self._ensure_auth_session_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                  event_id TEXT PRIMARY KEY,
                  actor_user_id TEXT,
                  actor_role TEXT,
                  action TEXT NOT NULL,
                  event_category TEXT,
                  severity TEXT,
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
            self._ensure_audit_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)")

    def _ensure_users_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(users)").fetchall()
        existing = {str(r["name"]) for r in rows}
        if "role" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'viewer'")
        if "status" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "created_by_user_id" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN created_by_user_id TEXT")
        if "created_by_username" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN created_by_username TEXT")
        if "admin_ticket_id" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN admin_ticket_id TEXT")
        if "admin_approval_token_hash" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN admin_approval_token_hash TEXT")
        if "business_unit" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN business_unit TEXT")
        if "department" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN department TEXT")
        if "user_type" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN user_type TEXT")
        if "data_scope" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN data_scope TEXT")

    def _ensure_audit_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(audit_logs)").fetchall()
        existing = {str(r["name"]) for r in rows}
        if "event_category" not in existing:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN event_category TEXT")
        if "severity" not in existing:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN severity TEXT")
        if "prev_event_hash" not in existing:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN prev_event_hash TEXT")
        if "event_hash" not in existing:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN event_hash TEXT")
        if "hash_kid" not in existing:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN hash_kid TEXT")

    def _ensure_auth_session_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(auth_sessions)").fetchall()
        existing = {str(r["name"]) for r in rows}
        if "last_seen_at" not in existing:
            conn.execute("ALTER TABLE auth_sessions ADD COLUMN last_seen_at TEXT")
            conn.execute("UPDATE auth_sessions SET last_seen_at=issued_at WHERE last_seen_at IS NULL OR last_seen_at=''")

    def register(self, username: str, password: str) -> dict[str, Any]:
        return self.create_user_with_role(username=username, password=password, role="viewer")

    def create_user_with_role(
        self,
        username: str,
        password: str,
        role: str = "viewer",
        created_by_user_id: str | None = None,
        created_by_username: str | None = None,
        admin_ticket_id: str | None = None,
        admin_approval_token_hash: str | None = None,
        business_unit: str | None = None,
        department: str | None = None,
        user_type: str | None = None,
        data_scope: str | None = None,
    ) -> dict[str, Any]:
        username = _validate_username(username)
        password = _validate_password(password)
        role = _validate_role(role)
        user_id = uuid.uuid4().hex
        salt_hex = secrets.token_hex(16)
        password_hash = _hash_password(password, salt_hex)
        now = _iso(_now())
        business_unit = _normalize_classification_value(business_unit)
        department = _normalize_classification_value(department)
        user_type = _normalize_classification_value(user_type)
        data_scope = _normalize_classification_value(data_scope)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users(
                      user_id, username, salt, password_hash, role, status,
                      created_by_user_id, created_by_username, admin_ticket_id, admin_approval_token_hash,
                      business_unit, department, user_type, data_scope, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        salt_hex,
                        password_hash,
                        role,
                        "active",
                        (created_by_user_id or "").strip() or None,
                        (created_by_username or "").strip() or None,
                        (admin_ticket_id or "").strip() or None,
                        (admin_approval_token_hash or "").strip() or None,
                        business_unit,
                        department,
                        user_type,
                        data_scope,
                        now,
                    ),
                )
        except sqlite3.IntegrityError:
            raise ValueError("username already exists")
        return {
            "user_id": user_id,
            "username": username,
            "role": role,
            "status": "active",
            "created_by_user_id": (created_by_user_id or "").strip() or None,
            "created_by_username": (created_by_username or "").strip() or None,
            "admin_ticket_id": (admin_ticket_id or "").strip() or None,
            "has_admin_approval_token": bool((admin_approval_token_hash or "").strip()),
            "business_unit": business_unit,
            "department": department,
            "user_type": user_type,
            "data_scope": data_scope,
        }

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
                "INSERT INTO auth_sessions(token, user_id, username, issued_at, last_seen_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token, str(row["user_id"]), str(row["username"]), _iso(issued_at), _iso(issued_at), _iso(expires_at)),
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

    def touch_session(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE auth_sessions SET last_seen_at=? WHERE token=?", (_iso(_now()), token))

    def list_users(self) -> list[dict[str, Any]]:
        now = _iso(_now())
        recent_10m = _iso(_now() - timedelta(minutes=10))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope,
                       CASE WHEN s.user_id IS NULL THEN 0 ELSE 1 END AS is_online,
                       CASE WHEN s10.user_id IS NULL THEN 0 ELSE 1 END AS is_online_10m,
                       u.created_at
                FROM users u
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ?
                ) s ON s.user_id = u.user_id
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ? AND COALESCE(last_seen_at, issued_at) >= ?
                ) s10 ON s10.user_id = u.user_id
                ORDER BY created_at DESC
                """,
                (now, now, recent_10m),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, username, role, status, created_by_user_id, created_by_username, admin_ticket_id,
                       business_unit, department, user_type, data_scope,
                       admin_approval_token_hash, created_at
                FROM users
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_user_role(self, user_id: str, role: str) -> dict[str, Any] | None:
        role = _validate_role(role)
        now = _iso(_now())
        recent_10m = _iso(_now() - timedelta(minutes=10))
        with self._connect() as conn:
            result = conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope,
                       CASE WHEN s.user_id IS NULL THEN 0 ELSE 1 END AS is_online,
                       CASE WHEN s10.user_id IS NULL THEN 0 ELSE 1 END AS is_online_10m,
                       u.created_at
                FROM users u
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ?
                ) s ON s.user_id = u.user_id
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ? AND COALESCE(last_seen_at, issued_at) >= ?
                ) s10 ON s10.user_id = u.user_id
                WHERE u.user_id=?
                """,
                (now, now, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_status(self, user_id: str, status: str) -> dict[str, Any] | None:
        status = _validate_status(status)
        now = _iso(_now())
        recent_10m = _iso(_now() - timedelta(minutes=10))
        with self._connect() as conn:
            result = conn.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
            if result.rowcount <= 0:
                return None
            if status == "disabled":
                conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope,
                       CASE WHEN s.user_id IS NULL THEN 0 ELSE 1 END AS is_online,
                       CASE WHEN s10.user_id IS NULL THEN 0 ELSE 1 END AS is_online_10m,
                       u.created_at
                FROM users u
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ?
                ) s ON s.user_id = u.user_id
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ? AND COALESCE(last_seen_at, issued_at) >= ?
                ) s10 ON s10.user_id = u.user_id
                WHERE u.user_id=?
                """,
                (now, now, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_admin_approval_token(
        self, user_id: str, admin_approval_token_hash: str | None, admin_ticket_id: str | None = None
    ) -> dict[str, Any] | None:
        now = _iso(_now())
        recent_10m = _iso(_now() - timedelta(minutes=10))
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE users SET admin_approval_token_hash=?, admin_ticket_id=COALESCE(?, admin_ticket_id) WHERE user_id=?",
                (
                    (admin_approval_token_hash or "").strip() or None,
                    (admin_ticket_id or "").strip() or None,
                    user_id,
                ),
            )
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope,
                       CASE WHEN s.user_id IS NULL THEN 0 ELSE 1 END AS is_online,
                       CASE WHEN s10.user_id IS NULL THEN 0 ELSE 1 END AS is_online_10m,
                       u.created_at
                FROM users u
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ?
                ) s ON s.user_id = u.user_id
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ? AND COALESCE(last_seen_at, issued_at) >= ?
                ) s10 ON s10.user_id = u.user_id
                WHERE u.user_id=?
                """,
                (now, now, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_password(self, user_id: str, password: str) -> dict[str, Any] | None:
        password = _validate_password(password)
        salt_hex = secrets.token_hex(16)
        password_hash = _hash_password(password, salt_hex)
        now = _iso(_now())
        recent_10m = _iso(_now() - timedelta(minutes=10))
        with self._connect() as conn:
            result = conn.execute("UPDATE users SET salt=?, password_hash=? WHERE user_id=?", (salt_hex, password_hash, user_id))
            if result.rowcount <= 0:
                return None
            # Force relogin after password reset.
            conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope,
                       CASE WHEN s.user_id IS NULL THEN 0 ELSE 1 END AS is_online,
                       CASE WHEN s10.user_id IS NULL THEN 0 ELSE 1 END AS is_online_10m,
                       u.created_at
                FROM users u
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ?
                ) s ON s.user_id = u.user_id
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ? AND COALESCE(last_seen_at, issued_at) >= ?
                ) s10 ON s10.user_id = u.user_id
                WHERE u.user_id=?
                """,
                (now, now, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_classification(
        self,
        user_id: str,
        business_unit: str | None = None,
        department: str | None = None,
        user_type: str | None = None,
        data_scope: str | None = None,
    ) -> dict[str, Any] | None:
        business_unit = _normalize_classification_value(business_unit)
        department = _normalize_classification_value(department)
        user_type = _normalize_classification_value(user_type)
        data_scope = _normalize_classification_value(data_scope)
        now = _iso(_now())
        recent_10m = _iso(_now() - timedelta(minutes=10))
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE users
                SET business_unit=?, department=?, user_type=?, data_scope=?
                WHERE user_id=?
                """,
                (business_unit, department, user_type, data_scope, user_id),
            )
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope,
                       CASE WHEN s.user_id IS NULL THEN 0 ELSE 1 END AS is_online,
                       CASE WHEN s10.user_id IS NULL THEN 0 ELSE 1 END AS is_online_10m,
                       u.created_at
                FROM users u
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ?
                ) s ON s.user_id = u.user_id
                LEFT JOIN (
                  SELECT DISTINCT user_id
                  FROM auth_sessions
                  WHERE expires_at > ? AND COALESCE(last_seen_at, issued_at) >= ?
                ) s10 ON s10.user_id = u.user_id
                WHERE u.user_id=?
                """,
                (now, now, recent_10m, user_id),
            ).fetchone()
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
        event_category, severity = _classify_audit_event(action=action, result=result)
        hash_kid, hash_secret = resolve_signing_secret()
        prev_event_hash = None
        event_hash = None
        with self._audit_lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                prev_row = conn.execute(
                    "SELECT event_hash FROM audit_logs WHERE event_hash IS NOT NULL AND event_hash <> '' ORDER BY created_at DESC, event_id DESC LIMIT 1"
                ).fetchone()
                prev_event_hash = str(prev_row["event_hash"]) if prev_row and prev_row["event_hash"] else None
                if hash_secret:
                    event_hash = sign_payload(
                        {
                            "event_id": event_id,
                            "created_at": created_at,
                            "prev_event_hash": prev_event_hash or "",
                            "actor_user_id": actor_user_id or "",
                            "actor_role": actor_role or "",
                            "action": action,
                            "event_category": event_category or "",
                            "severity": severity or "",
                            "resource_type": resource_type,
                            "resource_id": resource_id or "",
                            "result": result,
                            "ip": ip or "",
                            "user_agent": user_agent or "",
                            "detail": detail or "",
                        },
                        hash_secret,
                    )
                conn.execute(
                    """
                    INSERT INTO audit_logs(
                        event_id, actor_user_id, actor_role, action, event_category, severity,
                        resource_type, resource_id, result, ip, user_agent, detail, created_at,
                        prev_event_hash, event_hash, hash_kid
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        actor_user_id,
                        actor_role,
                        action,
                        event_category,
                        severity,
                        resource_type,
                        resource_id,
                        result,
                        ip,
                        user_agent,
                        detail,
                        created_at,
                        prev_event_hash,
                        event_hash,
                        hash_kid,
                    ),
                )
                conn.commit()
        return {
            "event_id": event_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action": action,
            "event_category": event_category,
            "severity": severity,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "ip": ip,
            "user_agent": user_agent,
            "detail": detail,
            "created_at": created_at,
            "prev_event_hash": prev_event_hash,
            "event_hash": event_hash,
            "hash_kid": hash_kid,
        }

    def list_audit_logs(
        self,
        limit: int = 200,
        actor_user_id: str | None = None,
        action_keyword: str | None = None,
        event_category: str | None = None,
        severity: str | None = None,
        result: str | None = None,
    ) -> list[dict[str, Any]]:
        cap = max(1, min(limit, 1000))
        where: list[str] = []
        params: list[Any] = []
        actor = (actor_user_id or "").strip()
        keyword = (action_keyword or "").strip().lower()
        category = (event_category or "").strip().lower()
        sev = (severity or "").strip().lower()
        res = (result or "").strip().lower()

        if actor:
            where.append("actor_user_id=?")
            params.append(actor)
        if keyword:
            where.append("lower(action) LIKE ?")
            params.append(f"%{keyword}%")
        if category:
            where.append("lower(COALESCE(event_category, ''))=?")
            params.append(category)
        if sev:
            where.append("lower(COALESCE(severity, ''))=?")
            params.append(sev)
        if res:
            where.append("lower(result)=?")
            params.append(res)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, actor_user_id, actor_role, action, event_category, severity,
                       resource_type, resource_id, result, ip, user_agent, detail, created_at,
                       prev_event_hash, event_hash, hash_kid
                FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, cap),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_active_sessions(self) -> int:
        now = _iso(_now())
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM auth_sessions WHERE expires_at > ?", (now,)).fetchone()
            return int(row["c"]) if row else 0
