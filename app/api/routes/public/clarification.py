"""Clarification API routes for enhanced query flow with proactive information gathering."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents.router.enhanced_service import EnhancedRouterService
from app.api.dependencies import (
    _history_store_for_user,
    _require_permission,
    _require_user,
    _require_valid_session_id,
)
from app.domain.contracts import ClarificationContext
from app.orchestration.request import OrchestrationRequest, RequestScope

router = APIRouter(prefix="/api/v1/clarification", tags=["clarification"])


class ClarificationCheckRequest(BaseModel):
    """Request to check if clarification is needed."""

    question: str = Field(..., description="User's question")
    session_id: str = Field(..., description="Session ID")
    field_name: str | None = Field(None, description="Field name for user's answer")
    answer: str | None = Field(None, description="User's answer to clarification question")


class ClarificationResponse(BaseModel):
    """Response with clarification decision."""

    action: str = Field(..., description="CONTINUE or NEED_CLARIFICATION")
    clarification: dict[str, Any] | None = Field(None, description="Next clarification question")
    context: dict[str, Any] = Field(..., description="Current clarification context")
    route: dict[str, Any] | None = Field(None, description="Route decision if CONTINUE")


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
    3. Execute enhanced router decision
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
    _require_permission(user, "query:run", request, "query")
    req.session_id = _require_valid_session_id(req.session_id)

    # Get history store for authenticated user
    history_store = _history_store_for_user(user)

    # Get or create session
    session = history_store.get_session(req.session_id)
    if session is None:
        _require_permission(user, "session:create", request, "session")
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

    # Build orchestration request
    orchestration_req = OrchestrationRequest(
        question=req.question,
        session_id=req.session_id,
        conversation=tuple(conversation_turns),
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    # Execute enhanced router
    router_service = EnhancedRouterService()
    decision = await router_service.route(orchestration_req, context)

    # If CONTINUE, reset clarification context
    if decision.action == "CONTINUE":
        history_store.reset_clarification_context(req.session_id)

    # Build response
    return ClarificationResponse(
        action=decision.action.value,
        clarification=(
            {
                "question": decision.clarification.question,
                "options": decision.clarification.options,
                "allow_custom_input": decision.clarification.allow_custom_input,
                "field_name": decision.clarification.field_name,
            }
            if decision.clarification
            else None
        ),
        context={
            "collected_info": decision.context.collected_info,
            "asked_questions": decision.context.asked_questions,
            "clarification_round": decision.context.clarification_round,
            "max_rounds": decision.context.max_rounds,
            "intent": decision.context.intent,
        },
        route=(
            {
                "intent": decision.intent,
                "route": decision.route,
                "confidence": decision.confidence,
                "requires_plan": decision.requires_plan,
                "allowed_capabilities": list(decision.allowed_capabilities),
                "reason": decision.reason,
            }
            if decision.action == "CONTINUE"
            else None
        ),
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
    _require_permission(user, "query:run", request, "query")
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
    _require_permission(user, "query:run", request, "query")
    session_id = _require_valid_session_id(session_id)

    history_store = _history_store_for_user(user)
    context = history_store.get_clarification_context(session_id)

    if context is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return context
