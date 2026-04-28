"""Admin security validation module.

Provides security checks for admin operations to prevent self-modification and privilege escalation.
"""
from typing import Any
from fastapi import HTTPException, Request


def check_self_modification(
    user_id: str,
    actor_user: dict[str, Any],
    operation: str,
    audit_callback: callable = None,
    request: Request = None
) -> None:
    """
    Check if admin is attempting to modify their own account.

    Args:
        user_id: Target user ID
        actor_user: User performing the operation
        operation: Operation type (for audit log)
        audit_callback: Audit log callback function
        request: FastAPI request object

    Raises:
        HTTPException: If self-modification is detected
    """
    actor_user_id = str(actor_user.get("user_id", ""))

    if user_id == actor_user_id:
        # Log audit trail
        if audit_callback and request:
            audit_callback(
                request,
                action=operation,
                resource_type="user",
                result="blocked_self_modification",
                user=actor_user,
                resource_id=user_id,
                detail=f"attempted self-modification: {operation}"
            )

        raise HTTPException(
            status_code=403,
            detail="cannot modify your own account"
        )


def check_admin_role_change(role: str) -> None:
    """
    Check if role change attempts to promote to admin.

    Args:
        role: Target role

    Raises:
        HTTPException: If attempting to promote to admin role
    """
    if str(role or "").strip().lower() == "admin":
        raise HTTPException(
            status_code=400,
            detail="admin role promotion is restricted; use /admin/users/create-admin"
        )


def validate_ticket_id(ticket_id: str) -> None:
    """
    Validate ticket ID format.

    Args:
        ticket_id: Ticket ID

    Raises:
        HTTPException: If format is invalid
    """
    import re

    # Ticket format: PROJECT-NUMBER (e.g., JIRA-123, TICKET-456)
    TICKET_PATTERN = re.compile(r'^[A-Z]+-\d+$')

    if not ticket_id or len(ticket_id) < 3:
        raise HTTPException(
            status_code=400,
            detail="ticket_id is required (minimum 3 characters)"
        )

    if not TICKET_PATTERN.match(ticket_id):
        raise HTTPException(
            status_code=400,
            detail="invalid ticket format (expected: PROJECT-NUMBER, e.g., JIRA-123)"
        )


def validate_reason(reason: str, min_length: int = 5) -> None:
    """
    Validate operation reason.

    Args:
        reason: Operation reason
        min_length: Minimum length

    Raises:
        HTTPException: If reason is too short
    """
    if not reason or len(reason) < min_length:
        raise HTTPException(
            status_code=400,
            detail=f"reason is required (minimum {min_length} characters)"
        )


def validate_approval_token_length(token: str, min_length: int = 12) -> None:
    """
    Validate approval token length.

    Args:
        token: Approval token
        min_length: Minimum length

    Raises:
        HTTPException: If token is too short
    """
    if not token or len(token) < min_length:
        raise HTTPException(
            status_code=400,
            detail=f"approval token must be at least {min_length} characters"
        )
