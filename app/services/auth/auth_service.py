import hashlib
import json
import secrets
import sqlite3
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.auth.audit_logger import AuditLogger
from app.services.auth.encryption import decrypt_api_settings_payload, encrypt_api_settings_payload
from app.services.auth.password_utils import generate_salt, hash_password
from app.services.auth.session_manager import SessionManager
from app.services.auth.user_manager import DEFAULT_CHAT_CREDITS, UserManager
from app.services.auth.utils import iso, now
from app.services.auth.validation import (
    normalize_classification_value,
    validate_password,
    validate_role,
    validate_username,
)


class PasswordChangeError(ValueError):
    """A password-change failure that is safe to present through the auth API."""

    def __init__(self, audit_detail: str, public_message: str, *, internal: bool = False):
        super().__init__(public_message)
        self.audit_detail = audit_detail
        self.internal = internal


class GoogleUserCreationError(RuntimeError):
    """A Google identity could not be provisioned after it was confirmed absent."""


class ChatCreditReservation:
    """One reserved chat credit that is refunded unless explicitly committed."""

    def __init__(self, *, charged: bool, remaining: int, refund: Callable[[], int | None]):
        self.charged = charged
        self.remaining = remaining
        self._refund = refund
        self._settled = not charged

    def commit(self) -> None:
        self._settled = True

    def close(self) -> None:
        if self._settled:
            return
        self._refund()
        self._settled = True

    def __enter__(self) -> "ChatCreditReservation":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


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
        with self._api_settings_key_lock:
            if self._api_settings_key is not None:
                return self._api_settings_key
            settings = get_settings()
            seed = str(getattr(settings, "api_settings_encryption_key", "") or "").strip()
            if not seed:
                # 安全修复：强制要求环境变量，禁止自动生成
                raise RuntimeError(
                    "API_SETTINGS_ENCRYPTION_KEY environment variable is required. "
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(48))' "
                    "and set it in the generated .runtime environment file. Auto-generation is disabled for security."
                )
            self._api_settings_key = hashlib.sha256(seed.encode("utf-8")).digest()
            return self._api_settings_key

    def _encrypt_api_settings_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return encrypt_api_settings_payload(payload, self._api_settings_data_key())

    def _decrypt_api_settings_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return decrypt_api_settings_payload(payload, self._api_settings_data_key())

    def _connect(self) -> sqlite3.Connection:
        settings = get_settings()
        # 安全修复：严格验证和类型转换，防止SQL注入
        try:
            timeout_s = float(getattr(settings, "sqlite_busy_timeout_seconds", 10) or 10)
            # 钳位到安全范围 [1.0, 3600.0]
            timeout_s = max(1.0, min(timeout_s, 3600.0))
        except (ValueError, TypeError):
            # 无效配置值，使用安全默认值
            timeout_s = 10.0

        timeout_ms = int(timeout_s * 1000)

        conn = sqlite3.connect(self.db_path, timeout=timeout_s, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # 安全修复：严格验证后才拼接PRAGMA语句
        # SQLite的PRAGMA不支持参数化查询，因此必须在严格验证后使用f-string
        # timeout_ms已经被验证为安全的整数，范围 [1000, 3600000]
        assert isinstance(timeout_ms, int) and 1000 <= timeout_ms <= 3600000, "timeout_ms validation failed"
        conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys = ON")
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
                  credit_balance INTEGER NOT NULL DEFAULT 10 CHECK(credit_balance >= 0),
                  created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_users_columns(conn)

            # 性能优化：添加用户名索引（已使用 COLLATE NOCASE）
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_identities (
                  provider TEXT NOT NULL,
                  email TEXT NOT NULL COLLATE NOCASE,
                  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY (provider, email)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_identities_user ON oauth_identities(user_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                  token TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                  username TEXT NOT NULL,
                  issued_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                )
                """
            )
            self._ensure_auth_session_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)")
            # HIGH PRIORITY FIX: Add indexes for query performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires ON auth_sessions(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_last_seen ON auth_sessions(last_seen_at)")
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

            # 安全修复：添加触发器防止审计日志被修改或删除
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS protect_audit_logs_update
                BEFORE UPDATE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'Audit logs are immutable and cannot be modified');
                END
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS protect_audit_logs_delete
                BEFORE DELETE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'Audit logs cannot be deleted');
                END
                """
            )
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
        if "display_name" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
        if "credit_balance" not in existing:
            conn.execute(
                f"ALTER TABLE users ADD COLUMN credit_balance INTEGER NOT NULL DEFAULT {DEFAULT_CHAT_CREDITS} "
                "CHECK(credit_balance >= 0)"
            )

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
            conn.execute(
                "UPDATE auth_sessions SET last_seen_at=issued_at WHERE last_seen_at IS NULL OR last_seen_at=''"
            )

    def register(self, username: str, password: str) -> dict[str, Any]:
        validate_password(password)
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
        with self._connect() as conn:
            return self._create_user_record(
                conn,
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

    @staticmethod
    def _validate_creation_password(password: str) -> str:
        """
        验证用户创建时的密码强度

        安全修复：移除降级验证逻辑，统一使用标准密码策略
        - 最小长度：12个字符（不再是8个）
        - 必须包含：小写字母、大写字母、数字、特殊字符
        - OAuth用户也必须遵守相同的密码策略

        Args:
            password: 待验证的密码

        Returns:
            验证通过的密码

        Raises:
            ValueError: 密码不符合安全策略
        """
        # 安全修复：统一使用标准验证，不再有降级路径
        return validate_password(password)

    def _create_user_record(
        self,
        conn: sqlite3.Connection,
        *,
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
        display_name: str | None = None,
        is_oauth_identity: bool = False,
    ) -> dict[str, Any]:
        """Create the user row used by both local registration and OAuth provisioning."""
        if is_oauth_identity:
            username = (username or "").strip()
            if not username:
                raise ValueError("missing OAuth email")
        else:
            # Public local registration keeps the established username policy.
            username = validate_username(username)
        password = self._validate_creation_password(password)
        role = validate_role(role)
        business_unit = normalize_classification_value(business_unit)
        department = normalize_classification_value(department)
        user_type = normalize_classification_value(user_type)
        data_scope = normalize_classification_value(data_scope)
        display_name = (display_name or "").strip() or None
        user_id = uuid.uuid4().hex
        salt_hex = generate_salt()
        password_hash = hash_password(password, salt_hex)
        created_at = iso(now())
        try:
            conn.execute(
                """
                INSERT INTO users(
                  user_id, username, salt, password_hash, role, status,
                  created_by_user_id, created_by_username, admin_ticket_id, admin_approval_token_hash,
                  business_unit, department, user_type, data_scope, display_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    display_name,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("username already exists") from exc
        return {
            "user_id": user_id,
            "username": username,
            "role": role,
            "status": "active",
            "credit_balance": DEFAULT_CHAT_CREDITS,
            "created_by_user_id": (created_by_user_id or "").strip() or None,
            "created_by_username": (created_by_username or "").strip() or None,
            "admin_ticket_id": (admin_ticket_id or "").strip() or None,
            "has_admin_approval_token": bool((admin_approval_token_hash or "").strip()),
            "business_unit": business_unit,
            "department": department,
            "user_type": user_type,
            "data_scope": data_scope,
            "display_name": display_name,
        }

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
            credit_balance=int(user.get("credit_balance", DEFAULT_CHAT_CREDITS)),
        )

    def logout(self, token: str) -> None:
        self.session_manager.delete_session(token)

    def update_user_display_name(self, user_id: str, display_name: str) -> dict[str, Any] | None:
        return self.user_manager.update_user_display_name(user_id, display_name)

    def change_password(
        self,
        *,
        user_id: str,
        username: str,
        old_password: str,
        new_password: str,
        current_token: str,
        role: str,
        status: str,
        credit_balance: int = DEFAULT_CHAT_CREDITS,
    ) -> dict[str, Any] | None:
        try:
            # Preserve the existing verification and session invalidation sequence.
            self.login(username, old_password)
        except ValueError as exc:
            raise PasswordChangeError("old_password_incorrect", "旧密码不正确") from exc

        try:
            validate_password(new_password)
        except ValueError as exc:
            raise PasswordChangeError(f"validation_failed: {exc}", str(exc)) from exc

        if old_password == new_password:
            raise PasswordChangeError("new_password_same_as_old", "新密码不能与旧密码相同")

        try:
            self.user_manager.update_user_password(user_id, new_password)
        except Exception as exc:
            raise PasswordChangeError(f"update_failed: {exc}", "密码更新失败", internal=True) from exc

        try:
            return self.session_manager.rotate_session_token(
                current_token,
                user_id,
                username,
                role,
                status,
                credit_balance,
            )
        except Exception:
            # A changed password remains valid even when session rotation cannot complete.
            return None

    def get_google_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized_email = self._normalize_oauth_email(email)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.display_name, u.credit_balance
                FROM oauth_identities i
                JOIN users u ON u.user_id = i.user_id
                WHERE i.provider = 'google' AND i.email = ?
                """,
                (normalized_email,),
            ).fetchone()
            if row:
                return self._public_google_user(dict(row), normalized_email)

            # Preserve access to accounts created before OAuth identities were stored.
            row = conn.execute(
                "SELECT user_id, username, role, status, display_name, credit_balance FROM users WHERE lower(username)=lower(?)",
                (normalized_email,),
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT OR IGNORE INTO oauth_identities(provider, email, user_id, created_at) VALUES (?, ?, ?, ?)",
                    ("google", normalized_email, row["user_id"], iso(now())),
                )
                return self._public_google_user(dict(row), normalized_email)

        return None

    def create_google_user(self, email: str, display_name: str) -> dict[str, Any]:
        user, _ = self._get_or_create_google_user(email, display_name)
        return user

    def complete_google_login(self, email: str, display_name: str) -> dict[str, Any]:
        """Resolve the Google identity and establish the callback session."""
        user, created = self._get_or_create_google_user(email, display_name)
        session = self.create_session_for_user(user)
        return {"user": user, "session": session, "created": created}

    @staticmethod
    def _normalize_oauth_email(email: str) -> str:
        normalized_email = (email or "").strip().casefold()
        if not normalized_email:
            raise ValueError("missing OAuth email")
        return normalized_email

    @staticmethod
    def _public_google_user(user: dict[str, Any], email: str) -> dict[str, Any]:
        """Expose the Google email identity, never an internal legacy surrogate."""
        return {**user, "username": email}

    def _get_or_create_google_user(self, email: str, display_name: str) -> tuple[dict[str, Any], bool]:
        normalized_email = self._normalize_oauth_email(email)
        normalized_display_name = (display_name or "").strip() or None
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.display_name, u.credit_balance
                FROM oauth_identities i
                JOIN users u ON u.user_id = i.user_id
                WHERE i.provider = 'google' AND i.email = ?
                """,
                (normalized_email,),
            ).fetchone()
            if row:
                return self._public_google_user(dict(row), normalized_email), False

            # Link legacy Google accounts without reinterpreting email as a local username.
            row = conn.execute(
                "SELECT user_id, username, role, status, display_name, credit_balance FROM users WHERE lower(username)=lower(?)",
                (normalized_email,),
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT INTO oauth_identities(provider, email, user_id, created_at) VALUES (?, ?, ?, ?)",
                    ("google", normalized_email, row["user_id"], iso(now())),
                )
                return self._public_google_user(dict(row), normalized_email), False

            try:
                user = self._create_user_record(
                    conn,
                    username=normalized_email,
                    password=f"GoogleOAuth1!{secrets.token_urlsafe(32)}",
                    role="viewer",
                    display_name=normalized_display_name,
                    is_oauth_identity=True,
                )
                conn.execute(
                    "INSERT INTO oauth_identities(provider, email, user_id, created_at) VALUES (?, ?, ?, ?)",
                    ("google", normalized_email, user["user_id"], iso(now())),
                )
            except Exception as exc:
                raise GoogleUserCreationError(str(exc)) from exc
            return self._public_google_user(user, normalized_email), True

    def create_session_for_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return self.session_manager.create_session(
            user_id=str(user["user_id"]),
            username=str(user["username"]),
            role=str(user["role"]),
            status=str(user["status"]),
            credit_balance=int(user.get("credit_balance", DEFAULT_CHAT_CREDITS)),
        )

    def get_user_by_token(self, token: str, include_disabled: bool = False) -> dict[str, Any] | None:
        return self.session_manager.get_user_by_token(token, include_disabled=include_disabled)

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

    def reserve_chat_credit(self, user_id: str) -> dict[str, Any]:
        return self.user_manager.reserve_chat_credit(user_id)

    def chat_credit_reservation(self, user_id: str) -> ChatCreditReservation:
        reserved = self.reserve_chat_credit(user_id)
        return ChatCreditReservation(
            charged=bool(reserved["charged"]),
            remaining=int(reserved["remaining"]),
            refund=lambda: self.refund_chat_credit(user_id),
        )

    def refund_chat_credit(self, user_id: str) -> int | None:
        return self.user_manager.refund_chat_credit(user_id)

    def add_user_credits(self, user_id: str, amount: int) -> dict[str, Any] | None:
        return self.user_manager.add_user_credits(user_id, amount)

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

            conn.execute("UPDATE users SET settings = ? WHERE user_id = ?", (json.dumps(settings), user_id))
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
