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
    if not register_limiter.try_acquire(register_key):
        _audit(request, action="auth.register", resource_type="auth", result="blocked", detail="register_rate_limited")
        raise rate_limited("too many register attempts, retry later")
    try:
        user = auth_service.register(req.username, req.password)
    except ValueError as exc:
        _audit(request, action="auth.register", resource_type="auth", result="failed", detail=str(exc))
        raise bad_request(str(exc))
    _audit(request, action="auth.register", resource_type="auth", result="success", resource_id=user["user_id"])
    return AuthUser(**user)


@router.post("/login", response_model=AuthLoginResponse)
def login(req: AuthCredentials, request: Request, response: Response):
    ip = _client_ip(request)
    username_key = normalize_string(req.username, lowercase=True) or "unknown"
    login_key = f"login::{ip}::{username_key}"
    if login_limiter.is_limited(login_key):
        # 获取限流详细信息
        limit_info = login_limiter.get_limit_info(login_key)

        _audit(request, action="auth.login", resource_type="auth", result="blocked", detail="login_rate_limited")

        # 构建友好的错误消息
        retry_minutes = limit_info["retry_after"] // 60
        retry_seconds = limit_info["retry_after"] % 60

        if retry_minutes > 0:
            time_msg = f"{retry_minutes}分{retry_seconds}秒" if retry_seconds > 0 else f"{retry_minutes}分钟"
        else:
            time_msg = f"{retry_seconds}秒"

        error_detail = {
            "error": "rate_limited",
            "message": f"登录尝试次数过多，请在{time_msg}后重试",
            "retry_after_seconds": limit_info["retry_after"],
            "attempts_used": limit_info["attempts_used"],
            "max_attempts": limit_info["max_attempts"],
            "window_seconds": limit_info["window_seconds"],
            "suggestion": "如果忘记密码，请使用'忘记密码'功能重置",
        }

        raise HTTPException(
            status_code=429,
            detail=error_detail,
            headers={"Retry-After": str(limit_info["retry_after"])}
        )
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
    _audit(
        request, action="auth.logout", resource_type="auth", result="success", user=user, resource_id=user["user_id"]
    )
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
    _audit(
        request,
        action="profile.updated",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail="profile_updated",
    )
    return AuthUser(**updated_user)


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    response: Response,
    auth: tuple[dict[str, Any], str] = Depends(_require_user_and_token),
):
    """
    修改用户密码（需要验证旧密码）

    改进后的处理流程：
    1. 验证旧密码
    2. 修改密码
    3. 尝试轮换token
    4. 如果轮换失败，明确告知用户需要重新登录
    """
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
            credit_balance=int(user.get("credit_balance", 10)),
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

    # 判断token轮换是否成功
    if new_session:
        # 成功轮换，更新cookie
        _set_auth_cookie(response, new_session["token"])
        _audit(
            request,
            action="auth.change_password",
            resource_type="auth",
            result="success",
            user=user,
            resource_id=user_id,
            detail="password_changed_token_rotated",
        )
        return {
            "ok": True,
            "message": "密码已成功更改",
            "token_rotated": True,
        }
    else:
        # 密码已改但token轮换失败
        # 清除现有cookie，强制用户重新登录
        _clear_auth_cookie(response)
        _audit(
            request,
            action="auth.change_password",
            resource_type="auth",
            result="success_needs_reauth",
            user=user,
            resource_id=user_id,
            detail="password_changed_token_rotation_failed",
        )
        # 返回特殊状态码和明确消息
        return {
            "ok": True,
            "message": "密码已成功更改，请重新登录",
            "token_rotated": False,
            "requires_relogin": True,  # 前端可以根据此字段自动跳转到登录页
            "reason": "为了安全，密码修改后需要重新认证",
        }


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
        return RedirectResponse(url="/login?error=invalid_state&hint=csrf_expired&message=登录会话已过期，请重新尝试")
    if state_error == "security_check_failed":
        _audit(
            request,
            action="auth.google_callback",
            resource_type="auth",
            result="blocked",
            detail=f"ip_mismatch: {stored_ip} != {current_ip}",
        )
        return RedirectResponse(url="/login?error=security_check_failed&hint=ip_mismatch&message=网络环境发生变化，请重新登录")

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
            return RedirectResponse(url="/login?error=no_email&hint=missing_email&message=Google账号未关联邮箱，请使用其他登录方式")

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
            return RedirectResponse(url="/login?error=registration_failed&hint=account_creation&message=无法创建账号，请联系管理员或使用其他登录方式")
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
        return RedirectResponse(url="/login?error=oauth_failed&hint=network_timeout&message=Google登录超时，请检查网络后重试")
