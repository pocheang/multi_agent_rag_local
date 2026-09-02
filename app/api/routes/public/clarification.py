"""Clarification API routes for enhanced query flow with proactive information gathering."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents.clarification.service import ClarificationAgentService
from app.agents.router.service import RouterAgentService
from app.api.dependencies import (
    _history_store_for_user,
    _require_permission,
    _require_user,
    _require_valid_session_id,
)
from app.domain.contracts import ClarificationContext, ClarificationQuestion
from app.orchestration.request import OrchestrationRequest, RequestActor, RequestScope
from app.services.security.rbac import Permission

router = APIRouter(prefix="/api/v1/clarification", tags=["clarification"])


class ClarificationCheckRequest(BaseModel):
    """Request to check if clarification is needed."""

    question: str = Field(..., min_length=1, max_length=20_000, description="User's question")
    session_id: str = Field(..., min_length=1, max_length=128, description="Session ID")
    field_name: str | None = Field(
        None,
        pattern=r"^[a-z][a-z0-9_]{0,63}$",
        description="Field name for user's answer",
    )
    answer: str | None = Field(None, min_length=1, max_length=4_000, description="User's answer")
    workflow_thread_id: str | None = Field(None, min_length=1, max_length=512)
    resume_token: str | None = Field(None, min_length=1, max_length=256)


class ClarificationResponse(BaseModel):
    """Response with clarification decision."""

    action: Literal["CONTINUE", "NEED_CLARIFICATION"]
    clarification: ClarificationQuestion | None = Field(None, description="Next clarification question")
    context: ClarificationContext = Field(..., description="Current clarification context")
    route: dict[str, Any] | None = Field(None, description="Route decision if CONTINUE")
    complete_query: str | None = Field(None, description="Original query enriched with confirmed fields")
    workflow_thread_id: str = Field(..., description="Tenant-scoped clarification thread")
    resume_token: str | None = Field(None, description="Signed resume correlation token when configured")


@router.post("/check", response_model=ClarificationResponse)
async def check_clarification(
    req: ClarificationCheckRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
) -> ClarificationResponse:
    """Check if clarification is needed for a query.

    Flow:
    1. If user provided an answer, update clarification context
    2. Get current clarification context from session
    3. Execute the clarification agent
    4. Return CONTINUE or NEED_CLARIFICATION with next question

    Args:
        req: Clarification check request
        request: FastAPI request
        user: Authenticated user

    Returns:
        Clarification response with action and context

    Raises:
        HTTPException: If session not found
    """
    _require_permission(user, Permission.QUERY_RUN, request, "query")
    req.session_id = _require_valid_session_id(req.session_id)
    tenant_id = str(user.get("tenant_id", "") or user.get("user_id", "") or "")
    user_id = str(user.get("user_id", "") or "")
    workflow_thread_id = ":".join((tenant_id, user_id, req.session_id))
    clarification_service = ClarificationAgentService()
    if req.workflow_thread_id and req.workflow_thread_id != workflow_thread_id:
        raise HTTPException(status_code=409, detail="Clarification workflow thread does not match this session")
    if req.resume_token is not None and not clarification_service.resume_token_is_valid(
        workflow_thread_id,
        req.resume_token,
    ):
        raise HTTPException(status_code=409, detail="Invalid clarification resume token")
    if bool(req.field_name) != bool(req.answer):
        raise HTTPException(status_code=422, detail="field_name and answer must be submitted together")

    # Get history store for authenticated user
    history_store = _history_store_for_user(user)

    # Get or create session
    session = history_store.get_session(req.session_id)
    if session is None:
        _require_permission(user, Permission.SESSION_CREATE, request, "session")
        session = history_store.create_session(session_id=req.session_id)

    # If user provided an answer, update clarification context
    if req.field_name and req.answer:
        history_store.update_clarification_context(
            req.session_id,
            req.field_name,
            req.answer,
        )
        session = history_store.get_session(req.session_id)

    # Get clarification context
    ctx_data = session.get("clarification_context", {})
    if not isinstance(ctx_data, dict):
        ctx_data = {
            "collected_info": {},
            "asked_questions": [],
            "clarification_round": 0,
            "max_rounds": 10,
            "intent": "",
            "original_query": "",
        }
    context = ClarificationContext(**ctx_data)

    # Build conversation from history
    messages = session.get("messages", [])
    conversation_turns = []
    from app.orchestration.request import ConversationTurn

    for msg in messages[-5:]:  # Last 5 messages for context
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role and content:
            conversation_turns.append(ConversationTurn(role=role, content=content))

    # Build orchestration request with the same identity used by the main workflow.
    orchestration_req = OrchestrationRequest(
        question=req.question,
        session_id=req.session_id,
        conversation=tuple(conversation_turns),
        actor=RequestActor(
            user_id=user_id,
            tenant_id=tenant_id,
            username=str(user.get("username", "") or ""),
            role=str(user.get("role", "viewer") or "viewer"),
            permissions=frozenset(str(value) for value in user.get("permissions", ()) or ()),
        ),
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    result = await clarification_service.clarify(
        orchestration_req,
        context=context,
        workflow_thread_id=workflow_thread_id,
    )
    history_store.set_clarification_context(req.session_id, result.context.model_dump(mode="json"))

    route_decision = None
    if result.action == "continue":
        complete_request = orchestration_req.model_copy(
            update={"question": result.complete_query or orchestration_req.question}
        )
        route_decision = await RouterAgentService().route(complete_request)

    # If CONTINUE, reset clarification context
    if result.action == "continue":
        history_store.reset_clarification_context(req.session_id)

    # Build response
    return ClarificationResponse(
        action="NEED_CLARIFICATION" if result.action == "ask" else "CONTINUE",
        clarification=(
            {
                "question": result.question.question,
                "options": result.question.options,
                "allow_custom_input": result.question.allow_custom_input,
                "field_name": result.question.field_name,
            }
            if result.question
            else None
        ),
        context={
            "collected_info": result.context.collected_info,
            "asked_questions": result.context.asked_questions,
            "clarification_round": result.context.clarification_round,
            "max_rounds": result.context.max_rounds,
            "intent": result.context.intent,
            "original_query": result.context.original_query,
        },
        route=(
            {
                "intent": route_decision.intent,
                "route": route_decision.route,
                "confidence": route_decision.confidence,
                "requires_plan": route_decision.requires_plan,
                "allowed_capabilities": list(route_decision.allowed_capabilities),
                "reason": route_decision.reason,
            }
            if route_decision is not None
            else None
        ),
        complete_query=result.complete_query,
        workflow_thread_id=workflow_thread_id,
        resume_token=clarification_service.issue_resume_token(workflow_thread_id),
    )


@router.post("/reset/{session_id}")
async def reset_clarification(
    session_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, str]:
    """Reset clarification context for a session.

    Useful when user wants to start over or skip clarification.

    Args:
        session_id: Session ID
        request: FastAPI request
        user: Authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If session not found or permission denied
    """
    _require_permission(user, Permission.QUERY_RUN, request, "query")
    session_id = _require_valid_session_id(session_id)

    history_store = _history_store_for_user(user)
    result = history_store.reset_clarification_context(session_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "success", "message": "Clarification context reset"}


@router.get("/context/{session_id}")
async def get_clarification_context(
    session_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, Any]:
    """Get current clarification context for a session.

    Args:
        session_id: Session ID
        request: FastAPI request
        user: Authenticated user

    Returns:
        Clarification context

    Raises:
        HTTPException: If session not found or permission denied
    """
    _require_permission(user, Permission.QUERY_RUN, request, "query")
    session_id = _require_valid_session_id(session_id)

    history_store = _history_store_for_user(user)
    context = history_store.get_clarification_context(session_id)

    if context is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return context
