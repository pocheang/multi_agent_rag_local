"""Enhanced query endpoint with clarification support."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.agents.router.enhanced_service import EnhancedRouterService
from app.api.dependencies import (
    _history_store_for_user,
    _require_permission,
    _require_user,
    _reserve_chat_credit,
)
from app.domain.contracts import ClarificationContext, RouterAction
from app.orchestration.request import ConversationTurn, OrchestrationRequest, RequestScope

router = APIRouter(prefix="/api/v1/query", tags=["enhanced_query"])


class EnhancedQueryRequest(BaseModel):
    """Enhanced query request with clarification support."""

    question: str = Field(..., description="User's question")
    session_id: str = Field(..., description="Session ID")
    use_web_fallback: bool = Field(default=False, description="Enable web fallback")
    use_reasoning: bool = Field(default=False, description="Enable reasoning")
    agent_class_hint: str | None = Field(None, description="Agent class hint")
    retrieval_strategy: str | None = Field(None, description="Retrieval strategy")

    # Clarification-related fields
    field_name: str | None = Field(None, description="Field name for clarification answer")
    answer: str | None = Field(None, description="User's clarification answer")


class EnhancedQueryResponse(BaseModel):
    """Enhanced query response."""

    status: str = Field(..., description="Status: 'clarification_needed' or 'completed'")

    # Clarification fields (when status='clarification_needed')
    clarification: dict[str, Any] | None = Field(None, description="Clarification question")
    context: dict[str, Any] | None = Field(None, description="Clarification context")

    # Query result fields (when status='completed')
    answer: str | None = Field(None, description="Final answer")
    citations: list[dict[str, Any]] | None = Field(None, description="Citations")
    route: dict[str, Any] | None = Field(None, description="Route decision")
    execution_metadata: dict[str, Any] | None = Field(None, description="Execution metadata")


@router.post("/enhanced", response_model=EnhancedQueryResponse)
async def enhanced_query(
    req: EnhancedQueryRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
) -> EnhancedQueryResponse:
    """Execute enhanced query with clarification support.

    Flow:
    1. Check if clarification is needed (EnhancedRouter)
    2. If NEED_CLARIFICATION: return clarification question
    3. If CONTINUE: execute full query pipeline
    4. Return result

    Args:
        req: Enhanced query request
        request: FastAPI request
        user: Authenticated user

    Returns:
        Enhanced query response with clarification or result
    """
    _require_permission(user, "query:execute", request, "query")

    history_store = _history_store_for_user(user)

    # Get or create session
    session = history_store.get_session(req.session_id)
    if session is None:
        session = history_store.create_session(session_id=req.session_id)

    # If user provided clarification answer, update context
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
    for msg in messages[-5:]:  # Last 5 messages
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role and content:
            conversation_turns.append(ConversationTurn(role=role, content=content))

    # Build orchestration request for router check
    orchestration_req = OrchestrationRequest(
        question=req.question,
        session_id=req.session_id,
        conversation=tuple(conversation_turns),
        use_reasoning=req.use_reasoning,
        use_web_fallback=req.use_web_fallback,
        source_scope=RequestScope(agent_class_hint=req.agent_class_hint),
        retrieval_strategy=req.retrieval_strategy,
    )

    # Execute enhanced router
    enhanced_router = EnhancedRouterService()
    decision = await enhanced_router.route(orchestration_req, context)

    # If clarification needed, return immediately
    if decision.action == RouterAction.NEED_CLARIFICATION:
        return EnhancedQueryResponse(
            status="clarification_needed",
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
        )

    # Information is sufficient, reset clarification and execute query
    history_store.reset_clarification_context(req.session_id)

    # Execute full query pipeline
    from app.pipeline.contracts import PipelineRequest
    from app.pipeline.profiles import PipelineProfile
    from app.pipeline.rag_pipeline import RAGPipeline

    pipeline = RAGPipeline()
    pipeline_request = PipelineRequest(
        question=req.question,
        session_id=req.session_id,
        profile=PipelineProfile.STANDARD,
        use_web_fallback=req.use_web_fallback,
        use_reasoning=req.use_reasoning,
        agent_class_hint=req.agent_class_hint,
        retrieval_strategy=req.retrieval_strategy,
    )

    with _reserve_chat_credit(request, user, "enhanced_query") as credit:
        result = await pipeline.execute(pipeline_request)

        # Save user message
        history_store.add_message(req.session_id, "user", req.question)

        # Save assistant message
        history_store.add_message(
            req.session_id,
            "assistant",
            result.answer,
            metadata={
                "route": result.route.route,
                "confidence": result.route.confidence,
                "citations": [c.model_dump() for c in result.citations],
            },
        )

        response = EnhancedQueryResponse(
            status="completed",
            answer=result.answer,
            citations=[
                {
                    "source": c.source,
                    "content": c.content,
                    "document_id": c.document_id,
                    "page": c.page,
                }
                for c in result.citations
            ],
            route={
                "route": result.route.route,
                "reason": result.route.reason,
                "confidence": result.route.confidence,
            },
            execution_metadata=dict(result.execution_metadata),
        )
        credit.commit()
        return response
