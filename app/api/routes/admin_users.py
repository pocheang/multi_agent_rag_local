"""Admin user management routes for the Multi-Agent Local RAG API."""
import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import (
    auth_service,
    _audit,
    _require_user,
    _require_permission,
    settings,
)
from app.core.schemas import (
    AdminCreateAdminRequest,
    AdminResetApprovalTokenRequest,
    AdminResetPasswordRequest,
    AdminRoleUpdateRequest,
    AdminStatusUpdateRequest,
    AdminUserClassificationUpdateRequest,
    AdminUserSummary,
    AuditLogEntry,
)
from app.services.log_buffer import list_captured_logs
from app.services.admin_token_tracker import token_tracker, validate_admin_approval_token, get_token_tracker
from app.services.admin_rate_limit import rate_limiter
from app.services.admin_security import check_self_modification
from app.api.utils.admin_helpers import validate_and_check_approval_token, handle_service_exception

router = APIRouter(prefix="/admin", tags=["admin"])


def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    """Validate the admin approval token against configured plain/hash values."""
    candidate = str(token or "").strip()
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
    configured_plain = str(getattr(settings, "admin_create_approval_token", "") or "").strip()
    if not configured_hash and not configured_plain:
        return False, "missing"
    if not candidate:
        return False, "empty"
    if configured_hash:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
        return hmac.compare_digest(digest, configured_hash), "hash"
    return hmac.compare_digest(candidate, configured_plain), "plain"

@router.get("/users", response_model=list[AdminUserSummary])


def admin_list_users(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")
    rows = auth_service.list_users()
    return [AdminUserSummary(**x) for x in rows]


@router.get("")
def admin_page(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")
    return {"ok": True, "message": "admin portal"}


@router.patch("/users/{user_id}/role", response_model=AdminUserSummary)
def admin_update_user_role(user_id: str, req: AdminRoleUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # SECURITY: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.role_update", _audit, request)

    if str(req.role or "").strip().lower() == "admin":
        raise HTTPException(status_code=400, detail="admin role promotion is restricted; use /admin/users/create-admin")
    try:
        row = auth_service.update_user_role(user_id=user_id, role=req.role)
    except ValueError as e:
        _audit(request, action="admin.user.role_update", resource_type="user", result="failed", user=user, resource_id=user_id, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    _audit(
        request,
        action="admin.user.role_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=f"role={row['role']}",
    )
    return AdminUserSummary(**row)


@router.post("/users/create-admin", response_model=AdminUserSummary)
def admin_create_user_as_admin(req: AdminCreateAdminRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")

    # SECURITY: Input validation FIRST (before token validation)
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()

    if len(ticket_id) < 3:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    # Validate ticket format: PROJECT-NUMBER (e.g., JIRA-123)
    if "-" not in ticket_id or len(ticket_id.split("-")[0]) < 2 or not ticket_id.split("-")[-1].isdigit():
        raise HTTPException(status_code=400, detail="invalid ticket format (expected: PROJECT-NUMBER)")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="reason is required")
    if len(new_admin_approval_token) < 12:
        raise HTTPException(status_code=400, detail="approval token must be at least 12 chars")

    # SECURITY: Validate approval token with single-use tracking
    actor_user_id = str(user.get("user_id", ""))
    approval_token = req.approval_token or ""
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()

    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        token_tracker
    )

    if not token_ok:
        _audit(
            request,
            action="admin.user.create_admin",
            resource_type="user",
            result="failed",
            user=user,
            detail=f"approval_failed; mode={token_mode}",
        )
        raise HTTPException(status_code=403, detail="unauthorized")
    new_admin_approval_hash = hashlib.sha256(new_admin_approval_token.encode("utf-8")).hexdigest()
    try:
        row = auth_service.create_user_with_role(
            username=req.username,
            password=req.password,
            role="admin",
            created_by_user_id=str(user.get("user_id", "")),
            created_by_username=str(user.get("username", "")),
            admin_ticket_id=ticket_id,
            admin_approval_token_hash=new_admin_approval_hash,
        )
    except ValueError as e:
        _audit(
            request,
            action="admin.user.create_admin",
            resource_type="user",
            result="failed",
            user=user,
            detail=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
    _audit(
        request,
        action="admin.user.create_admin",
        resource_type="user",
        result="success",
        user=user,
        resource_id=row["user_id"],
        detail=f"username={row['username']}; mode={token_mode}; ticket={ticket_id}; reason={reason}",
    )
    return AdminUserSummary(**row)


@router.post("/users/{user_id}/reset-approval-token", response_model=AdminUserSummary)
def admin_reset_user_approval_token(
    user_id: str,
    req: AdminResetApprovalTokenRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # SECURITY: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.reset_approval_token", _audit, request)

    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if str(target.get("role", "")).lower() != "admin":
        raise HTTPException(status_code=400, detail="target user is not admin")

    # SECURITY: Input validation FIRST
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()

    if len(ticket_id) < 3:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    # Validate ticket format: PROJECT-NUMBER (e.g., JIRA-123)
    if "-" not in ticket_id or len(ticket_id.split("-")[0]) < 2 or not ticket_id.split("-")[-1].isdigit():
        raise HTTPException(status_code=400, detail="invalid ticket format (expected: PROJECT-NUMBER)")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="reason is required")
    if len(new_admin_approval_token) < 12:
        raise HTTPException(status_code=400, detail="approval token must be at least 12 chars")

    # SECURITY: Validate approval token with single-use tracking
    actor_user_id = str(user.get("user_id", ""))
    approval_token = req.approval_token or ""
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()

    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        token_tracker
    )

    if not token_ok:
        _audit(
            request,
            action="admin.user.reset_approval_token",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"approval_failed; mode={token_mode}",
        )
        raise HTTPException(status_code=403, detail="unauthorized")

    token_hash = hashlib.sha256(new_admin_approval_token.encode("utf-8")).hexdigest()
    row = auth_service.update_user_admin_approval_token(
        user_id=user_id,
        admin_approval_token_hash=token_hash,
        admin_ticket_id=ticket_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.reset_approval_token",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"target={target.get('username', '-')}; mode={token_mode}; ticket={ticket_id}; reason={reason}; "
            f"actor={user.get('username', '-')}"
        ),
    )
    return AdminUserSummary(**row)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserSummary)
def admin_reset_user_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # SECURITY: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.reset_password", _audit, request)

    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    # SECURITY: Input validation FIRST
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_password = req.new_password or ""

    if len(ticket_id) < 3:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="reason is required")

    # SECURITY: Validate approval token with single-use tracking
    actor_user_id = str(user.get("user_id", ""))
    approval_token = req.approval_token or ""
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()

    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        token_tracker
    )

    if not token_ok:
        _audit(
            request,
            action="admin.user.reset_password",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"approval_failed; mode={token_mode}",
        )
        raise HTTPException(status_code=403, detail="unauthorized")
    try:
        row = auth_service.update_user_password(user_id=user_id, password=new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.reset_password",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"target={target.get('username', '-')}; mode={token_mode}; ticket={ticket_id}; reason={reason}; "
            f"actor={user.get('username', '-')}"
        ),
    )
    return AdminUserSummary(**row)


@router.patch("/users/{user_id}/status", response_model=AdminUserSummary)
def admin_update_user_status(user_id: str, req: AdminStatusUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # SECURITY: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.status_update", _audit, request)

    try:
        row = auth_service.update_user_status(user_id=user_id, status=req.status)
    except ValueError as e:
        _audit(request, action="admin.user.status_update", resource_type="user", result="failed", user=user, resource_id=user_id, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    _audit(
        request,
        action="admin.user.status_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=f"status={row['status']}",
    )
    return AdminUserSummary(**row)


@router.patch("/users/{user_id}/classification", response_model=AdminUserSummary)
def admin_update_user_classification(
    user_id: str,
    req: AdminUserClassificationUpdateRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # SECURITY: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.classification_update", _audit, request)

    try:
        row = auth_service.update_user_classification(
            user_id=user_id,
            business_unit=req.business_unit,
            department=req.department,
            user_type=req.user_type,
            data_scope=req.data_scope,
        )
    except ValueError as e:
        _audit(
            request,
            action="admin.user.classification_update",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    _audit(
        request,
        action="admin.user.classification_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"business_unit={row.get('business_unit') or '-'}; department={row.get('department') or '-'}; "
            f"user_type={row.get('user_type') or '-'}; data_scope={row.get('data_scope') or '-'}"
        ),
    )
    return AdminUserSummary(**row)


@router.get("/audit-logs", response_model=list[AuditLogEntry])
def admin_list_audit_logs(
    request: Request,
    limit: int = 200,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    event_category: str | None = None,
    severity: str | None = None,
    result: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = auth_service.list_audit_logs(
        limit=limit,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
        event_category=event_category,
        severity=severity,
        result=result,
    )
    return [AuditLogEntry(**x) for x in rows]


@router.get("/system-logs")
def admin_system_logs(
    request: Request,
    limit: int = 200,
    level: str | None = None,
    logger: str | None = None,
    keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = list_captured_logs(limit=limit, level=level, logger_keyword=logger, keyword=keyword)
    return {"items": rows, "count": len(rows)}


