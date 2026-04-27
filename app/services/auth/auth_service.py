import hashlib
import json
import secrets
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.auth.audit_logger import AuditLogger
from app.services.auth.encryption import encrypt_api_settings_payload, decrypt_api_settings_payload
from app.services.auth.session_manager import SessionManager
from app.services.auth.user_manager import UserManager
from app.services.auth.utils import iso, now
from app.services.auth.validation import validate_username


class AuthDBService:
    def __init__(self, db_path: Path | None = None, token_ttl_hours: int | None = None):
        settings = get_settings()
        self.db_path = db_path or settings.app_db_path
        self.token_ttl_hours = token_ttl_hours or settings.auth_token_ttl_hours
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._api_settings_key_lock = threading.Lock()
        self._api_settings_key: bytes | None = None
        self._init_schema()

        self.user_manager = UserManager(self._connect)
        self.session_manager = SessionManager(self._connect, self.token_ttl_hours)
        self.audit_logger = AuditLogger(self._connect)

    def _api_settings_key_path(self) -> Path:
        return self.db_path.parent / ".api_settings.key"

    def _api_settings_data_key(self) -> bytes:
        if self._api_settings_key is not None:
            return self._api_settings_key
        with self._api_settings_key_lock:
            if self._api_settings_key is not None:
                return self._api_settings_key
            settings = get_settings()
            seed = str(getattr(settings, "api_settings_encryption_key", "") or "").strip()
            if not seed:
                key_path = self._api_settings_key_path()
                if key_path.exists():
                    seed = str(key_path.read_text(encoding="utf-8") or "").strip()
                if not seed:
                    seed = secrets.token_urlsafe(48)
                    key_path.write_text(seed, encoding="utf-8")
            self._api_settings_key = hashlib.sha256(seed.encode("utf-8")).digest()
            return self._api_settings_key

    def _encrypt_api_settings_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return encrypt_api_settings_payload(payload, self._api_settings_data_key())

    def _decrypt_api_settings_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return decrypt_api_settings_payload(payload, self._api_settings_data_key())

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )

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
        if "settings" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN settings TEXT")

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
        return self.user_manager.create_user(
            username=username,
            password=password,
            role=role,
            created_by_user_id=created_by_user_id,
            created_by_username=created_by_username,
            admin_ticket_id=admin_ticket_id,
            admin_approval_token_hash=admin_approval_token_hash,
            business_unit=business_unit,
            department=department,
            user_type=user_type,
            data_scope=data_scope,
        )

    def login(self, username: str, password: str) -> dict[str, Any]:
        username = validate_username(username)
        user = self.user_manager.authenticate(username, password)
        if user is None:
            raise ValueError("invalid credentials")
        return self.session_manager.create_session(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            status=user["status"],
        )

    def logout(self, token: str) -> None:
        self.session_manager.delete_session(token)

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        return self.session_manager.get_user_by_token(token)

    def touch_session(self, token: str) -> None:
        self.session_manager.touch_session(token)

    def list_users(self) -> list[dict[str, Any]]:
        return self.user_manager.list_users()

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        return self.user_manager.get_user_profile(user_id)

    def update_user_role(self, user_id: str, role: str) -> dict[str, Any] | None:
        return self.user_manager.update_user_role(user_id, role)

    def update_user_status(self, user_id: str, status: str) -> dict[str, Any] | None:
        return self.user_manager.update_user_status(user_id, status)

    def update_user_admin_approval_token(
        self, user_id: str, admin_approval_token_hash: str | None, admin_ticket_id: str | None = None
    ) -> dict[str, Any] | None:
        return self.user_manager.update_user_admin_approval_token(user_id, admin_approval_token_hash, admin_ticket_id)

    def update_user_password(self, user_id: str, password: str) -> dict[str, Any] | None:
        return self.user_manager.update_user_password(user_id, password)

    def update_user_classification(
        self,
        user_id: str,
        business_unit: str | None = None,
        department: str | None = None,
        user_type: str | None = None,
        data_scope: str | None = None,
    ) -> dict[str, Any] | None:
        return self.user_manager.update_user_classification(user_id, business_unit, department, user_type, data_scope)

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
        return self.audit_logger.add_audit_log(
            action=action,
            resource_type=resource_type,
            result=result,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            resource_id=resource_id,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )

    def list_audit_logs(
        self,
        limit: int = 200,
        actor_user_id: str | None = None,
        action_keyword: str | None = None,
        event_category: str | None = None,
        severity: str | None = None,
        result: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.audit_logger.list_audit_logs(limit, actor_user_id, action_keyword, event_category, severity, result)

    def count_active_sessions(self) -> int:
        return self.session_manager.count_active_sessions()

    def get_user_metadata(self, user_id: str, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT settings FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row or not row["settings"]:
                return None
            try:
                settings_data = json.loads(row["settings"])
                value = settings_data.get(key)
                if key == "api_settings" and isinstance(value, dict):
                    return self._decrypt_api_settings_payload(value)
                return value
            except (json.JSONDecodeError, AttributeError):
                return None

    def set_user_metadata(self, user_id: str, key: str, value: dict[str, Any]) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT settings FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError("user not found")

            try:
                settings = json.loads(row["settings"]) if row["settings"] else {}
            except (json.JSONDecodeError, AttributeError):
                settings = {}

            to_store = dict(value)
            if key == "api_settings":
                to_store = self._encrypt_api_settings_payload(to_store)
            settings[key] = to_store

            conn.execute(
                "UPDATE users SET settings = ? WHERE user_id = ?",
                (json.dumps(settings), user_id)
            )
            conn.commit()

    def get_system_metadata(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
            if not row or not row["value"]:
                return None
            try:
                value = json.loads(row["value"])
                if key == "global_model_settings" and isinstance(value, dict):
                    return self._decrypt_api_settings_payload(value)
                return value
            except (json.JSONDecodeError, AttributeError):
                return None

    def set_system_metadata(self, key: str, value: dict[str, Any]) -> None:
        to_store = dict(value)
        if key == "global_model_settings":
            to_store = self._encrypt_api_settings_payload(to_store)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                (key, json.dumps(to_store), iso(now())),
            )
            conn.commit()
