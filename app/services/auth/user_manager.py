import hmac
import secrets
import sqlite3
import uuid
from datetime import timedelta
from typing import Any

from app.services.auth.password_utils import hash_password, verify_password, generate_salt
from app.services.auth.utils import now, iso
from app.services.auth.validation import (
    validate_username,
    validate_password,
    validate_role,
    validate_status,
    normalize_classification_value,
)


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
    ) -> dict[str, Any]:
        username = validate_username(username)
        password = validate_password(password)
        role = validate_role(role)
        user_id = uuid.uuid4().hex
        salt_hex = generate_salt()
        password_hash = hash_password(password, salt_hex)
        now_ts = iso(now())
        business_unit = normalize_classification_value(business_unit)
        department = normalize_classification_value(department)
        user_type = normalize_classification_value(user_type)
        data_scope = normalize_classification_value(data_scope)
        try:
            with self.conn_factory() as conn:
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
            "created_by_user_id": (created_by_user_id or "").strip() or None,
            "created_by_username": (created_by_username or "").strip() or None,
            "admin_ticket_id": (admin_ticket_id or "").strip() or None,
            "has_admin_approval_token": bool((admin_approval_token_hash or "").strip()),
            "business_unit": business_unit,
            "department": department,
            "user_type": user_type,
            "data_scope": data_scope,
        }

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        username = validate_username(username)
        with self.conn_factory() as conn:
            row = conn.execute(
                "SELECT user_id, username, salt, password_hash, role, status FROM users WHERE lower(username)=lower(?)",
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
            }

    def list_users(self) -> list[dict[str, Any]]:
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
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
                (now_ts, now_ts, recent_10m),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        with self.conn_factory() as conn:
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_status(self, user_id: str, status: str) -> dict[str, Any] | None:
        status = validate_status(status)
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
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
                (now_ts, now_ts, recent_10m, user_id),
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None

    def update_user_password(self, user_id: str, password: str) -> dict[str, Any] | None:
        password = validate_password(password)
        salt_hex = generate_salt()
        password_hash = hash_password(password, salt_hex)
        now_ts = iso(now())
        recent_10m = iso(now() - timedelta(minutes=10))
        with self.conn_factory() as conn:
            result = conn.execute("UPDATE users SET salt=?, password_hash=? WHERE user_id=?", (salt_hex, password_hash, user_id))
            if result.rowcount <= 0:
                return None
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
                (now_ts, now_ts, recent_10m, user_id),
            ).fetchone()
            return dict(row) if row else None
