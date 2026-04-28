"""Admin operation rate limiting configuration.

Provides rate limiting for sensitive admin operations to prevent brute-force attacks and abuse.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_limiter() -> Limiter:
    """
    Get rate limiter instance.

    Returns:
        Limiter instance
    """
    return Limiter(key_func=get_remote_address)


# Rate limit configuration
RATE_LIMITS = {
    # Admin creation - very strict
    "admin_create": "1/hour",  # Max 1 admin creation per hour

    # Approval token reset - strict
    "approval_token_reset": "3/hour",  # Max 3 token resets per hour

    # Password reset - moderate
    "password_reset": "5/hour",  # Max 5 password resets per hour

    # Role update - moderate
    "role_update": "10/hour",  # Max 10 role updates per hour

    # Status update - lenient
    "status_update": "20/hour",  # Max 20 status updates per hour

    # List queries - lenient
    "list_users": "100/minute",  # Max 100 user list queries per minute

    # Audit log queries - lenient
    "audit_logs": "50/minute",  # Max 50 audit log queries per minute
}


def get_rate_limit(operation: str) -> str:
    """
    Get rate limit for specified operation.

    Args:
        operation: Operation type

    Returns:
        Rate limit string (e.g., "1/hour")
    """
    return RATE_LIMITS.get(operation, "10/minute")  # Default limit
