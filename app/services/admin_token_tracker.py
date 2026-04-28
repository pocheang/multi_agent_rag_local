"""Admin approval token tracking service.

Tracks approval token usage to implement single-use and expiration mechanisms.
"""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class AdminTokenTracker:
    """Admin approval token tracker."""

    def __init__(self, expiry_hours: int = 24):
        """
        Initialize token tracker.

        Args:
            expiry_hours: Token expiration time in hours
        """
        self._used_tokens: dict[str, dict] = {}  # token_hash -> {used_at, used_by}
        self._expiry_hours = expiry_hours
        logger.info(f"AdminTokenTracker initialized with {expiry_hours}h expiry")

    def is_token_used(self, token_hash: str) -> bool:
        """
        Check if token has been used.

        Args:
            token_hash: SHA256 hash of the token

        Returns:
            True if token has been used and not expired
        """
        if token_hash in self._used_tokens:
            used_info = self._used_tokens[token_hash]
            used_at = used_info.get("used_at")

            if used_at:
                age = datetime.utcnow() - used_at
                if age.total_seconds() < self._expiry_hours * 3600:
                    logger.warning(
                        f"Token reuse attempt detected: hash={token_hash[:8]}..., "
                        f"originally used by {used_info.get('used_by')} at {used_at}"
                    )
                    return True
                else:
                    # Expired, clean up
                    logger.info(f"Cleaning expired token: hash={token_hash[:8]}...")
                    del self._used_tokens[token_hash]

        return False

    def mark_token_used(self, token_hash: str, user_id: str) -> None:
        """
        Mark token as used.

        Args:
            token_hash: SHA256 hash of the token
            user_id: User ID who used the token
        """
        self._used_tokens[token_hash] = {
            "used_at": datetime.utcnow(),
            "used_by": user_id
        }
        logger.info(f"Token marked as used: hash={token_hash[:8]}..., user={user_id}")

    def cleanup_expired(self) -> int:
        """
        Clean up expired token records.

        Returns:
            Number of tokens cleaned up
        """
        now = datetime.utcnow()
        expired = [
            token_hash for token_hash, info in self._used_tokens.items()
            if (now - info["used_at"]).total_seconds() >= self._expiry_hours * 3600
        ]

        for token_hash in expired:
            del self._used_tokens[token_hash]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired tokens")

        return len(expired)

    def get_usage_stats(self) -> dict:
        """
        Get token usage statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_used_tokens": len(self._used_tokens),
            "expiry_hours": self._expiry_hours
        }


def validate_admin_approval_token(
    token: str,
    configured_hash: str,
    actor_user_id: str,
    tracker: AdminTokenTracker
) -> tuple[bool, str]:
    """
    Validate admin approval token (timing-attack resistant, single-use).

    Args:
        token: Token to validate
        configured_hash: Configured token hash
        actor_user_id: User ID performing the operation
        tracker: Token tracker instance

    Returns:
        (is_valid, mode) tuple
        - is_valid: Whether token is valid
        - mode: Validation mode ("hash", "missing", "empty", "already_used")
    """
    candidate = str(token or "").strip()

    # Check configuration
    if not configured_hash:
        # Perform dummy comparison to maintain constant time
        dummy_digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
        hmac.compare_digest(dummy_digest, "0" * 64)
        return False, "missing"

    if not candidate:
        # Perform dummy comparison to maintain constant time
        hmac.compare_digest("", configured_hash)
        return False, "empty"

    # Calculate token hash
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()

    # Check if token has been used
    if tracker.is_token_used(digest):
        # Still perform comparison to maintain constant time
        hmac.compare_digest(digest, configured_hash)
        return False, "already_used"

    # Validate token
    is_valid = hmac.compare_digest(digest, configured_hash)

    if is_valid:
        # Mark token as used
        tracker.mark_token_used(digest, actor_user_id)

    return is_valid, "hash"


# Global token tracker instance
_global_tracker: Optional[AdminTokenTracker] = None


def get_token_tracker() -> AdminTokenTracker:
    """
    Get global token tracker instance.

    Returns:
        AdminTokenTracker instance
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = AdminTokenTracker(expiry_hours=24)
    return _global_tracker


# Export global instance for convenience
token_tracker = get_token_tracker()
