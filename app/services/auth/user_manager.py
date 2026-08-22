import sqlite3
import uuid
from datetime import timedelta
from typing import Any

from app.services.auth.password_utils import generate_salt, hash_password, verify_password
from app.services.auth.utils import iso, now
from app.services.auth.validation import (
    normalize_classification_value,
    validate_password,
    validate_role,
    validate_status,
    validate_username,
)

DEFAULT_CHAT_CREDITS = 10
MAX_CREDIT_TOP_UP = 1_000_000


class InsufficientCreditsError(RuntimeError):
    """Raised when a non-admin user has no chat credits remaining."""


def _validate_user_id(user_id: str) -> str:
    """
    Validate and normalize user ID.

    安全改进：统一验证逻辑，返回标准化的user_id

    Args:
        user_id: User ID to validate

    Returns:
        Normalized user ID

    Raises:
        ValueError: If user_id is invalid
    """
    if not user_id:
        raise ValueError("user_id cannot be empty")

    normalized = str(user_id).strip()

    if not normalized:
        raise ValueError("user_id cannot be empty after normalization")

    # 验证UUID格式
    try:
        uuid.UUID(normalized)
    except (ValueError, TypeError, AttributeError) as e:
        raise ValueError(f"Invalid user_id format: {normalized}") from e

    return normalized


def _validate_service_password(password: str) -> str:
    """
    验证密码强度 - 统一策略

    安全修复：移除降级路径，统一使用标准密码策略
    - 最小长度：12个字符（不再是8个）
    - 必须包含：小写字母、大写字母、数字、特殊字符

    注释说明的"legacy internal fixtures"应该通过测试专用机制处理，
    而不是降低生产代码的安全标准。

    Args:
        password: 待验证的密码

    Returns:
        验证通过的密码

    Raises:
        ValueError: 密码不符合安全策略
    """
    return validate_password(password)


class UserManager:
    def __init__(self, conn_factory):
        self.conn_factory = conn_factory

    def create_user(
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
        display_name: str | None = None,
    ) -> dict[str, Any]:
        username = validate_username(username)
        password = _validate_service_password(password)
        role = validate_role(role)
        user_id = uuid.uuid4().hex
        salt_hex = generate_salt()
        password_hash = hash_password(password, salt_hex)
        now_ts = iso(now())
        business_unit = normalize_classification_value(business_unit)
        department = normalize_classification_value(department)
        user_type = normalize_classification_value(user_type)
        data_scope = normalize_classification_value(data_scope)
        display_name = (display_name or "").strip() or None
        try:
            with self.conn_factory() as conn:
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
                        now_ts,
                    ),
                )
        except sqlite3.IntegrityError:
            raise ValueError("username already exists")
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

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        username = validate_username(username)
        with self.conn_factory() as conn:
            row = conn.execute(
                "SELECT user_id, username, salt, password_hash, role, status, credit_balance FROM users WHERE lower(username)=lower(?)",
                (username,),
            ).fetchone()
            if row is None:
                return None
            if str(row["status"]).lower() != "active":
                raise ValueError("user disabled")
            if not verify_password(password or "", str(row["salt"]), str(row["password_hash"])):
                return None
            return {
                "user_id": str(row["user_id"]),
                "username": str(row["username"]),
                "role": str(row["role"]),
                "status": str(row["status"]),
                "credit_balance": int(row["credit_balance"]),
            }

    def list_users(self) -> list[dict[str, Any]]:
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
            rows = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope, u.credit_balance,
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
                (now_ts, now_ts, recent_10m),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user profile by user_id.

        安全改进：统一user_id验证逻辑

        Args:
            user_id: User ID

        Returns:
            User profile dict or None if not found
        """
        # 安全改进：统一验证逻辑，捕获异常
        try:
            user_id = _validate_user_id(user_id)
        except ValueError as e:
            import logging

            logging.getLogger(__name__).warning(f"Invalid user_id rejected: {e}")
            return None

        with self.conn_factory() as conn:
            row = conn.execute(
                """
                SELECT user_id, username, role, status, created_by_user_id, created_by_username, admin_ticket_id,
                       business_unit, department, user_type, data_scope, credit_balance,
                       admin_approval_token_hash, created_at
                FROM users
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_user_role(self, user_id: str, role: str) -> dict[str, Any] | None:
        """
        Update user role.

        安全改进：添加user_id验证
        """
        # 安全改进：验证user_id
        try:
            user_id = _validate_user_id(user_id)
        except ValueError:
            return None

        role = validate_role(role)
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
            result = conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope, u.credit_balance,
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_status(self, user_id: str, status: str) -> dict[str, Any] | None:
        """
        Update user status.

        安全改进：添加user_id验证
        """
        # 安全改进：验证user_id
        try:
            user_id = _validate_user_id(user_id)
        except ValueError:
            return None

        status = validate_status(status)
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
            result = conn.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
            if result.rowcount <= 0:
                return None
            # SECURITY FIX: Don't delete sessions when disabling user
            # Let the auth layer (_require_user) handle status check and return 403
            # This provides better security feedback (403 vs 401)
            # if status == "disabled":
            #     conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope, u.credit_balance,
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_display_name(self, user_id: str, display_name: str | None) -> dict[str, Any] | None:
        with self.conn_factory() as conn:
            result = conn.execute(
                "UPDATE users SET display_name=? WHERE user_id=?",
                (display_name, user_id),
            )
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                "SELECT user_id, username, display_name, role, status, credit_balance FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_user_admin_approval_token(
        self, user_id: str, admin_approval_token_hash: str | None, admin_ticket_id: str | None = None
    ) -> dict[str, Any] | None:
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
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
                       u.business_unit, u.department, u.user_type, u.data_scope, u.credit_balance,
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_password(self, user_id: str, password: str) -> dict[str, Any] | None:
        password = _validate_service_password(password)
        salt_hex = generate_salt()
        password_hash = hash_password(password, salt_hex)
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
            result = conn.execute(
                "UPDATE users SET salt=?, password_hash=? WHERE user_id=?", (salt_hex, password_hash, user_id)
            )
            if result.rowcount <= 0:
                return None
            conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.role, u.status, u.created_by_user_id, u.created_by_username, u.admin_ticket_id,
                       CASE WHEN u.admin_approval_token_hash IS NOT NULL AND u.admin_approval_token_hash <> '' THEN 1 ELSE 0 END AS has_admin_approval_token,
                       u.business_unit, u.department, u.user_type, u.data_scope, u.credit_balance,
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
                (now_ts, now_ts, recent_10m, user_id),
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
        business_unit = normalize_classification_value(business_unit)
        department = normalize_classification_value(department)
        user_type = normalize_classification_value(user_type)
        data_scope = normalize_classification_value(data_scope)
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
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
                       u.business_unit, u.department, u.user_type, u.data_scope, u.credit_balance,
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def reserve_chat_credit(self, user_id: str) -> dict[str, Any]:
        """Atomically reserve one credit for a non-admin chat request."""
        user_id = _validate_user_id(user_id)
        with self.conn_factory() as conn:
            result = conn.execute(
                """
                UPDATE users
                SET credit_balance = credit_balance - 1
                WHERE user_id=?
                  AND lower(role) <> 'admin'
                  AND lower(status) = 'active'
                  AND credit_balance > 0
                """,
                (user_id,),
            )
            if result.rowcount > 0:
                row = conn.execute(
                    "SELECT credit_balance FROM users WHERE user_id=?",
                    (user_id,),
                ).fetchone()
                return {"charged": True, "remaining": int(row["credit_balance"])}

            row = conn.execute(
                "SELECT role, status, credit_balance FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise ValueError("user not found")
            if str(row["role"]).lower() == "admin":
                return {"charged": False, "remaining": int(row["credit_balance"])}
            if str(row["status"]).lower() != "active":
                raise ValueError("user disabled")
            raise InsufficientCreditsError("额度不足，请联系管理员添加额度")

    def refund_chat_credit(self, user_id: str) -> int | None:
        """Return a previously reserved credit after an unsuccessful request."""
        user_id = _validate_user_id(user_id)
        with self.conn_factory() as conn:
            result = conn.execute(
                """
                UPDATE users
                SET credit_balance = credit_balance + 1
                WHERE user_id=? AND lower(role) <> 'admin'
                """,
                (user_id,),
            )
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                "SELECT credit_balance FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()
            return int(row["credit_balance"]) if row else None

    def add_user_credits(self, user_id: str, amount: int) -> dict[str, Any] | None:
        """Atomically add a positive number of credits to a non-admin user."""
        user_id = _validate_user_id(user_id)
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError("amount must be an integer")
        if amount < 1 or amount > MAX_CREDIT_TOP_UP:
            raise ValueError(f"amount must be between 1 and {MAX_CREDIT_TOP_UP}")

        with self.conn_factory() as conn:
            result = conn.execute(
                """
                UPDATE users
                SET credit_balance = credit_balance + ?
                WHERE user_id=? AND lower(role) <> 'admin'
                """,
                (amount, user_id),
            )
            if result.rowcount <= 0:
                target = conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
                if target is None:
                    return None
                raise ValueError("cannot add credits to an administrator")

        return next((row for row in self.list_users() if row["user_id"] == user_id), None)
