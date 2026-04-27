"""Prompt management routes for the Multi-Agent Local RAG API."""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from app.api.dependencies import (    prompt_store,    _require_user,    _audit,    _require_permission,    _normalize_prompt_fields,    _resolve_effective_agent_class,)
from app.core.schemas import (    PromptCheckRequest,    PromptCheckResponse,    PromptTemplate,    PromptTemplateCreateRequest,    PromptTemplateUpdateRequest,)
from app.services.prompt_checker import check_and_enhance_prompt

router = APIRouter(prefix="/prompts", tags=["prompts"])

@router.get("", response_model=list[PromptTemplate])


def list_prompts(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    rows = prompt_store.list_prompts(user["user_id"])
    return [PromptTemplate(**x) for x in rows]


@router.post("", response_model=PromptTemplate)
def create_prompt(req: PromptTemplateCreateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    agent_class = _resolve_effective_agent_class(f"{title}\n{content}", None)
    row = prompt_store.create_prompt(user_id=user["user_id"], title=title, content=content, agent_class=agent_class)
    _audit(request, action="prompt.create", resource_type="prompt", result="success", user=user, resource_id=row["prompt_id"])
    return PromptTemplate(**row)


@router.post("/check", response_model=PromptCheckResponse)
def check_prompt(req: PromptCheckRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    checked = check_and_enhance_prompt(title=title, content=content, use_reasoning=req.use_reasoning)
    _audit(request, action="prompt.check", resource_type="prompt", result="success", user=user)
    return PromptCheckResponse(**checked)


@router.patch("/{prompt_id}", response_model=PromptTemplate)
def update_prompt(prompt_id: str, req: PromptTemplateUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
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
        raise HTTPException(status_code=404, detail="prompt not found")
    _audit(request, action="prompt.update", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return PromptTemplate(**row)


@router.get("/{prompt_id}/versions")
def list_prompt_versions(prompt_id: str, request: Request, limit: int = 20, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    rows = prompt_store.list_versions(user_id=user["user_id"], prompt_id=prompt_id, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.post("/{prompt_id}/versions/{version_id}/approve")
def approve_prompt_version(prompt_id: str, version_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    row = prompt_store.approve_version(
        user_id=user["user_id"],
        prompt_id=prompt_id,
        version_id=version_id,
        approved_by=str(user.get("username", "")),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="prompt version not found")
    _audit(request, action="prompt.version.approve", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return row


@router.post("/{prompt_id}/versions/{version_id}/rollback", response_model=PromptTemplate)
def rollback_prompt_version(prompt_id: str, version_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    row = prompt_store.rollback_to_version(user_id=user["user_id"], prompt_id=prompt_id, version_id=version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="prompt version not found")
    _audit(request, action="prompt.version.rollback", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return PromptTemplate(**row)


@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    ok = prompt_store.delete_prompt(user_id=user["user_id"], prompt_id=prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="prompt not found")
    _audit(request, action="prompt.delete", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return {"ok": True, "prompt_id": prompt_id}
