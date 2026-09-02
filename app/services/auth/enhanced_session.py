"""
Enhanced Session Management with CSRF Token Binding

Provides secure session management with:
- CSRF token generation and validation
- Redis-backed session storage (with fallback to file)
- HttpOnly cookie support
- Session expiration and cleanup
"""

import json
import logging
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Session storage backend with Redis support and file fallback.
    """

    def __init__(self, redis_url: str | None = None, fallback_path: Path | None = None):
        """Initialize session store with Redis or file backend."""
        self.redis_client = None
        self.fallback_path = fallback_path or Path("./data/security/sessions.json")
        self.use_redis = False

        # Try to connect to Redis
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                self.use_redis = True
                logger.info(f"SessionStore: Using Redis at {redis_url}")
            except Exception as e:
                logger.warning(f"SessionStore: Redis unavailable ({e}), falling back to file storage")
                self.redis_client = None

        if not self.use_redis:
            self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"SessionStore: Using file storage at {self.fallback_path}")

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int = 86400) -> bool:
        """Store session data with TTL."""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(f"session:{key}", ttl_seconds, json.dumps(value))
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}, falling back to file")
                self.use_redis = False

        # File fallback
        sessions = self._load_file_sessions()
        sessions[key] = {"data": value, "expires_at": time.time() + ttl_seconds}
        return self._save_file_sessions(sessions)

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve session data."""
        if self.use_redis and self.redis_client:
            try:
                data = self.redis_client.get(f"session:{key}")
                return json.loads(data) if data else None
            except Exception as e:
                logger.warning(f"Redis get failed: {e}, falling back to file")
                self.use_redis = False

        # File fallback
        sessions = self._load_file_sessions()
        session = sessions.get(key)
        if session and session["expires_at"] > time.time():
            return session["data"]
        elif session:
            # Expired, remove it
            del sessions[key]
            self._save_file_sessions(sessions)
        return None

    def delete(self, key: str):
        """Delete session data."""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.delete(f"session:{key}")
                return
            except Exception:
                pass

        # File fallback
        sessions = self._load_file_sessions()
        if key in sessions:
            del sessions[key]
            self._save_file_sessions(sessions)

    def cleanup_expired(self):
        """Clean up expired sessions (file backend only)."""
        if self.use_redis:
            return  # Redis handles TTL automatically

        sessions = self._load_file_sessions()
        current_time = time.time()
        expired = [k for k, v in sessions.items() if v["expires_at"] <= current_time]

        if expired:
            for key in expired:
                del sessions[key]
            self._save_file_sessions(sessions)
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def _load_file_sessions(self) -> dict[str, dict]:
        """Load sessions from file."""
        if not self.fallback_path.exists():
            return {}
        try:
            with open(self.fallback_path) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_file_sessions(self, sessions: dict[str, dict]) -> bool:
        """Save sessions to file. Returns whether the write succeeded.

        It used to swallow the failure and return nothing, so `set()` reported
        success on a session it had not stored -- the caller had no way to know
        the login would not survive.
        """

        try:
            with open(self.fallback_path, "w") as f:
                json.dump(sessions, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
            return False


class EnhancedSessionManager:
    """
    Enhanced session manager with CSRF token binding.

    Features:
    - CSRF token generation and validation
    - Redis-backed session storage
    - HttpOnly cookie support
    - Automatic session cleanup
    """

    def __init__(
        self,
        redis_url: str | None = None,
        fallback_path: Path | None = None,
        session_ttl: int = 86400,  # 24 hours
    ):
        """Initialize enhanced session manager."""
        self.store = SessionStore(redis_url, fallback_path)
        self.session_ttl = session_ttl

    def create_session(
        self, user_id: str, username: str, role: str, additional_data: dict[str, Any] | None = None
    ) -> tuple[str, str]:
        """
        Create a new session with CSRF token.

        Returns:
            tuple[session_id, csrf_token]
        """
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_hex(32)

        session_data = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "csrf_token": csrf_token,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            **(additional_data or {}),
        }

        self.store.set(session_id, session_data, self.session_ttl)
        return session_id, csrf_token

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session data."""
        return self.store.get(session_id)

    def validate_csrf_token(self, session_id: str, csrf_token: str) -> bool:
        """
        Validate CSRF token against session.

        Returns:
            True if token is valid, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False

        stored_token = session.get("csrf_token")
        if not stored_token:
            return False

        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(stored_token, csrf_token)

    def refresh_session(self, session_id: str) -> bool:
        """Refresh session TTL and update last activity."""
        session = self.get_session(session_id)
        if not session:
            return False

        session["last_activity"] = datetime.utcnow().isoformat()
        self.store.set(session_id, session, self.session_ttl)
        return True

    def delete_session(self, session_id: str):
        """Delete session."""
        self.store.delete(session_id)

    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        self.store.cleanup_expired()


# Singleton instance
_session_manager: EnhancedSessionManager | None = None


def get_session_manager(redis_url: str | None = None, session_ttl: int = 86400) -> EnhancedSessionManager:
    """Get or create session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = EnhancedSessionManager(redis_url=redis_url, session_ttl=session_ttl)
    return _session_manager
