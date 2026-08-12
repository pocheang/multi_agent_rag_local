"""Authentication routes for the QueryMind API."""

from typing import Any

try:
    from authlib.integrations.starlette_client import OAuth
except ModuleNotFoundError:
    OAuth = None
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.dependencies import (
    _audit,
    _clear_auth_cookie,
    _client_ip,
    _require_user,
    _require_user_and_token,
    _set_auth_cookie,
    auth_service,
    login_limiter,
    register_limiter,
    settings,
)
from app.api.schemas import AuthCredentials, AuthLoginResponse, AuthUser
from app.api.transport.errors import (
    bad_request,
    internal_error,
    not_found,
    not_implemented,
    rate_limited,
    unauthorized,
)
from app.api.utils.string_utils import normalize_string
from app.services.auth.auth_service import GoogleUserCreationError, PasswordChangeError
from app.services.auth.oauth_state import OAuthStateStore


router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth setup
oauth = OAuth() if OAuth is not None else None
if oauth is not None and settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

oauth_state_store = OAuthStateStore(settings.redis_url)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    display_name: str


@router.post("/register", response_model=AuthUser)
def register(req: AuthCredentials, request: Request):
    ip = _client_ip(request)
    register_key = f"register::{ip}"
    if register_limiter.is_limited(register_key):
        _audit(request, action="auth.register", resource_type="auth", result="blocked", detail="register_rate_limited")
        raise rate_limited("too many register attempts, retry later")
    try:
        user = auth_service.register(req.username, req.password)
    except ValueError as exc:
        register_limiter.record(register_key)
        _audit(request, action="auth.register", resource_type="auth", result="failed", detail=str(exc))
        raise bad_request(str(exc))
    register_limiter.reset(register_key)
    _audit(request, action="auth.register", resource_type="auth", result="success", resource_id=user["user_id"])
    return AuthUser(**user)


@router.post("/login", response_model=AuthLoginResponse)
def login(req: AuthCredentials, request: Request, response: Response):
    ip = _client_ip(request)
    username_key = normalize_string(req.username, lowercase=True) or "unknown"
    login_key = f"login::{ip}::{username_key}"
    if login_limiter.is_limited(login_key):
        _audit(request, action="auth.login", resource_type="auth", result="blocked", detail="login_rate_limited")
        raise rate_limited("too many login attempts, retry later")
    try:
        payload = auth_service.login(req.username, req.password)
    except ValueError as exc:
        login_limiter.record(login_key)
        _audit(request, action="auth.login", resource_type="auth", result="failed", detail=str(exc))
        raise unauthorized("invalid credentials")
    login_limiter.reset(login_key)
    _audit(
        request,
        action="auth.login",
        resource_type="auth",
        result="success",
        resource_id=payload["user"]["user_id"],
        detail=f"user={payload['user']['username']}",
    )
    token_value = str(payload.get("token", "") or "")
    _set_auth_cookie(response, token_value)
    if not bool(getattr(settings, "auth_expose_token_in_response", False)):
        payload = {**payload, "token": ""}
    return AuthLoginResponse(**payload)


@router.post("/logout")
def logout(request: Request, response: Response, auth: tuple[dict[str, Any], str] = Depends(_require_user_and_token)):
    user, token = auth
    auth_service.logout(token)
    _clear_auth_cookie(response)
    _audit(request, action="auth.logout", resource_type="auth", result="success", user=user, resource_id=user["user_id"])
    return {"ok": True}


@router.get("/me", response_model=AuthUser)
def auth_me(user: dict[str, Any] = Depends(_require_user)):
    return AuthUser(**user)


@router.put("/profile", response_model=AuthUser)
def update_profile(
    req: UpdateProfileRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """Update user profile (display name)."""
    user_id = user["user_id"]
    updated_user = auth_service.update_user_display_name(user_id, req.display_name)
    if not updated_user:
        raise not_found("User")
    _audit(request, "profile_updated", user_id=user_id, details={"display_name": req.display_name})
    return AuthUser(**updated_user)


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    response: Response,
    auth: tuple[dict[str, Any], str] = Depends(_require_user_and_token),
):
    """Change user password (requires old password verification)."""
    user, token = auth
    user_id = user["user_id"]
    try:
        new_session = auth_service.change_password(
            user_id=user_id,
            username=user["username"],
            old_password=req.old_password,
            new_password=req.new_password,
            current_token=token,
            role=user["role"],
            status=user["status"],
        )
    except PasswordChangeError as exc:
        _audit(
            request,
            action="auth.change_password",
            resource_type="auth",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=exc.audit_detail,
        )
        if exc.internal:
            raise internal_error(str(exc))
        raise bad_request(str(exc))
    except Exception as exc:
        _audit(
            request,
            action="auth.change_password",
            resource_type="auth",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"update_failed: {exc}",
        )
        raise internal_error("密码更新失败")

    if new_session:
        _set_auth_cookie(response, new_session["token"])
    _audit(
        request,
        action="auth.change_password",
        resource_type="auth",
        result="success",
        user=user,
        resource_id=user_id,
    )
    return {"ok": True, "message": "密码已成功更改"}


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    """Initiate Google OAuth login flow."""
    if not oauth.google:
        raise not_implemented("Google OAuth 未配置")
    state = oauth_state_store.create({"ip": _client_ip(request)}, ttl_seconds=300)
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri, state=state)


@router.get("/google/callback")
async def google_callback(request: Request) -> RedirectResponse:
    """Handle Google OAuth callback."""
    if not oauth.google:
        raise not_implemented("Google OAuth 未配置")

    state = request.query_params.get("state")
    current_ip = _client_ip(request)
    state_error, stored_ip = oauth_state_store.consume(state, current_ip)
    if state_error == "invalid_state":
        _audit(
            request,
            action="auth.google_callback",
            resource_type="auth",
            result="blocked",
            detail="invalid_state",
        )
        return RedirectResponse(url="/login?error=invalid_state")
    if state_error == "security_check_failed":
        _audit(
            request,
            action="auth.google_callback",
            resource_type="auth",
            result="blocked",
            detail=f"ip_mismatch: {stored_ip} != {current_ip}",
        )
        return RedirectResponse(url="/login?error=security_check_failed")

    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info or not user_info.get("email"):
            _audit(
                request,
                action="auth.google_callback",
                resource_type="auth",
                result="failed",
                detail="no_email_in_response",
            )
            return RedirectResponse(url="/login?error=no_email")

        email = user_info["email"]
        name = user_info.get("name", email.split("@")[0])
        try:
            login_result = auth_service.complete_google_login(email, name)
        except GoogleUserCreationError as exc:
            _audit(
                request,
                action="auth.google_register",
                resource_type="auth",
                result="failed",
                detail=f"user_creation_failed: {exc}",
            )
            return RedirectResponse(url="/login?error=registration_failed")
        user = login_result["user"]
        if not login_result["created"]:
            _audit(
                request,
                action="auth.google_login",
                resource_type="auth",
                result="success",
                user=user,
                resource_id=user["user_id"],
                detail="existing_user",
            )
        else:
            _audit(
                request,
                action="auth.google_register",
                resource_type="auth",
                result="success",
                user=user,
                resource_id=user["user_id"],
                detail="new_user_created",
            )

        redirect = RedirectResponse(url="/app")
        _set_auth_cookie(redirect, login_result["session"]["token"])
        return redirect
    except Exception as exc:
        _audit(
            request,
            action="auth.google_callback",
            resource_type="auth",
            result="failed",
            detail=f"oauth_error: {exc}",
        )
        return RedirectResponse(url="/login?error=oauth_failed")
