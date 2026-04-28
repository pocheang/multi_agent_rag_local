"""Authentication routes for the Multi-Agent Local RAG API."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.dependencies import (
    _audit,
    _client_ip,
    _clear_auth_cookie,
    _require_user,
    _require_user_and_token,
    _set_auth_cookie,
    auth_service,
    login_limiter,
    register_limiter,
    settings,
)
from app.core.schemas import AuthCredentials, AuthLoginResponse, AuthUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthUser)
def register(req: AuthCredentials, request: Request):
    ip = _client_ip(request)
    register_key = f"register::{ip}"
    if register_limiter.is_limited(register_key):
        _audit(request, action="auth.register", resource_type="auth", result="blocked", detail="register_rate_limited")
        raise HTTPException(status_code=429, detail="too many register attempts, retry later")
    try:
        user = auth_service.register(req.username, req.password)
    except ValueError as e:
        register_limiter.record(register_key)
        _audit(request, action="auth.register", resource_type="auth", result="failed", detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    register_limiter.reset(register_key)
    _audit(request, action="auth.register", resource_type="auth", result="success", resource_id=user["user_id"])
    return AuthUser(**user)


@router.post("/login", response_model=AuthLoginResponse)
def login(req: AuthCredentials, request: Request, response: Response):
    ip = _client_ip(request)
    username_key = (req.username or "").strip().lower() or "unknown"
    login_key = f"login::{ip}::{username_key}"
    if login_limiter.is_limited(login_key):
        _audit(request, action="auth.login", resource_type="auth", result="blocked", detail="login_rate_limited")
        raise HTTPException(status_code=429, detail="too many login attempts, retry later")
    try:
        payload = auth_service.login(req.username, req.password)
    except ValueError as e:
        login_limiter.record(login_key)
        _audit(request, action="auth.login", resource_type="auth", result="failed", detail=str(e))
        raise HTTPException(status_code=401, detail="invalid credentials")
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
    _user, token = auth
    auth_service.logout(token)
    _clear_auth_cookie(response)
    _audit(request, action="auth.logout", resource_type="auth", result="success", user=_user, resource_id=_user["user_id"])
    return {"ok": True}


@router.get("/me", response_model=AuthUser)
def auth_me(user: dict[str, Any] = Depends(_require_user)):
    return AuthUser(**user)


