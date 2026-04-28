import secrets
from datetime import timedelta
from typing import Any

from app.services.auth.utils import now, iso, parse_iso


class SessionManager:
    def __init__(self, conn_factory, token_ttl_hours: int):
        self.conn_factory = conn_factory
        self.token_ttl_hours = token_ttl_hours

    def create_session(self, user_id: str, username: str, role: str, status: str) -> dict[str, Any]:
        token = secrets.token_urlsafe(40)
        issued_at = now()
        expires_at = issued_at + timedelta(hours=self.token_ttl_hours)
        with self.conn_factory() as conn:
            conn.execute(
                "INSERT INTO auth_sessions(token, user_id, username, issued_at, last_seen_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token, user_id, username, iso(issued_at), iso(issued_at), iso(expires_at)),
            )
        return {
            "token": token,
            "token_type": "bearer",
            "expires_at": iso(expires_at),
            "user": {
                "user_id": user_id,
                "username": username,
                "role": role,
                "status": status,
            },
        }

    def delete_session(self, token: str) -> None:
        with self.conn_factory() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with self.conn_factory() as conn:
            now_ts = now()
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
            if parse_iso(str(row["expires_at"])) <= now_ts:
                conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
                return None
            # SECURITY FIX: Return user even if not active, let auth layer handle status check
            # This ensures proper 403 response instead of 401 for disabled users
            return {
                "user_id": str(row["user_id"]),
                "username": str(row["username"]),
                "role": str(row["role"]),
                "status": str(row["status"]),
            }

    def touch_session(self, token: str) -> None:
        with self.conn_factory() as conn:
            conn.execute("UPDATE auth_sessions SET last_seen_at=? WHERE token=?", (iso(now()), token))

    def count_active_sessions(self) -> int:
        now_ts = iso(now())
        with self.conn_factory() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM auth_sessions WHERE expires_at > ?", (now_ts,)).fetchone()
            return int(row["c"]) if row else 0
