"""Prompt management routes for the QueryMind API."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import (
    _audit,
    _normalize_prompt_fields,
    _require_permission,
    _require_user,
    _resolve_effective_agent_class,
    prompt_store,
)
from app.api.schemas import (
    PromptCheckRequest,
    PromptCheckResponse,
    PromptTemplate,
    PromptTemplateCreateRequest,
    PromptTemplateUpdateRequest,
)
from app.api.transport.errors import not_found
from app.services.security.audit_actions import AuditAction
from app.services.security.prompt_checker import check_and_enhance_prompt
from app.services.security.rbac import Permission

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptTemplate])
def list_prompts(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.PROMPT_READ, request, "prompt")
    rows = prompt_store.list_prompts(user["user_id"])
    return [PromptTemplate(**x) for x in rows]


@router.post("", response_model=PromptTemplate)
def create_prompt(req: PromptTemplateCreateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.PROMPT_CREATE, request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    agent_class = _resolve_effective_agent_class(f"{title}\n{content}", None)
    row = prompt_store.create_prompt(user_id=user["user_id"], title=title, content=content, agent_class=agent_class)
    _audit(
        request,
        action=AuditAction.PROMPT_CREATE,
        resource_type="prompt",
        result="success",
        user=user,
        resource_id=row["prompt_id"],
    )
    return PromptTemplate(**row)


@router.post("/check", response_model=PromptCheckResponse)
def check_prompt(req: PromptCheckRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.PROMPT_READ, request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    checked = check_and_enhance_prompt(title=title, content=content, use_reasoning=req.use_reasoning)
    _audit(request, action=AuditAction.PROMPT_CHECK, resource_type="prompt", result="success", user=user)
    return PromptCheckResponse(**checked)


@router.patch("/{prompt_id}", response_model=PromptTemplate)
def update_prompt(
    prompt_id: str, req: PromptTemplateUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    _require_permission(user, Permission.PROMPT_EDIT, request, "prompt", resource_id=prompt_id)
    title, content = _normalize_prompt_fields(req.title, req.content)
    agent_class = _resolve_effective_agent_class(f"{title}\n{content}", None)
    row = prompt_store.update_prompt(
        user_id=user["user_id"],
        prompt_id=prompt_id,
        title=title,
        content=content,
        agent_class=agent_class,
    )
    if row is None:
        raise not_found("Prompt")
    _audit(
        request,
        action=AuditAction.PROMPT_UPDATE,
        resource_type="prompt",
        result="success",
        user=user,
        resource_id=prompt_id,
    )
    return PromptTemplate(**row)


@router.get("/{prompt_id}/versions")
def list_prompt_versions(
    prompt_id: str, request: Request, limit: int = 20, user: dict[str, Any] = Depends(_require_user)
):
    _require_permission(user, Permission.PROMPT_READ, request, "prompt", resource_id=prompt_id)
    rows = prompt_store.list_versions(user_id=user["user_id"], prompt_id=prompt_id, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.post("/{prompt_id}/versions/{version_id}/approve")
def approve_prompt_version(
    prompt_id: str, version_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    _require_permission(user, Permission.PROMPT_EDIT, request, "prompt", resource_id=prompt_id)
    row = prompt_store.approve_version(
        user_id=user["user_id"],
        prompt_id=prompt_id,
        version_id=version_id,
        approved_by=str(user.get("username", "")),
    )
    if row is None:
        raise not_found("Prompt version")
    _audit(
        request,
        action=AuditAction.PROMPT_VERSION_APPROVE,
        resource_type="prompt",
        result="success",
        user=user,
        resource_id=prompt_id,
    )
    return row


@router.post("/{prompt_id}/versions/{version_id}/rollback", response_model=PromptTemplate)
def rollback_prompt_version(
    prompt_id: str, version_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    _require_permission(user, Permission.PROMPT_EDIT, request, "prompt", resource_id=prompt_id)
    row = prompt_store.rollback_to_version(user_id=user["user_id"], prompt_id=prompt_id, version_id=version_id)
    if row is None:
        raise not_found("Prompt version")
    _audit(
        request,
        action=AuditAction.PROMPT_VERSION_ROLLBACK,
        resource_type="prompt",
        result="success",
        user=user,
        resource_id=prompt_id,
    )
    return PromptTemplate(**row)


@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.PROMPT_DELETE, request, "prompt", resource_id=prompt_id)
    ok = prompt_store.delete_prompt(user_id=user["user_id"], prompt_id=prompt_id)
    if not ok:
        raise not_found("Prompt")
    _audit(
        request,
        action=AuditAction.PROMPT_DELETE,
        resource_type="prompt",
        result="success",
        user=user,
        resource_id=prompt_id,
    )
    return {"ok": True, "prompt_id": prompt_id}
