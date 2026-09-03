"""
API routes for advanced RAG functionality.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.agents.rag.service import RetrievalFailureError
from app.agents.shared.config import get_vector_rag_config
from app.api.dependencies import (
    _build_memory_context_for_session,
    _history_store_for_user,
    _promote_long_term_memory,
    _recent_session_turns,
    _require_permission,
    _require_user,
    _require_valid_session_id,
    _reserve_chat_credit_async,
)
from app.api.deps.auth import require_admin
from app.api.deps.documents import _allowed_sources_for_user
from app.api.routes.internal.pipeline_contract import retrieval_summary
from app.api.transport.errors import internal_error, service_unavailable
from app.api.transport.middleware import record_grounding_support
from app.core.config import get_settings
from app.domain.advanced_rag import (
    AdvancedRAGResult,
    AnswerQuality,
    DecomposedQuery,
    PendingApprovalView,
    SubQueryResult,
)
from app.pipeline.contracts import (
    ConversationMessage,
    PipelineContext,
    PipelineRequest,
    PipelineResult,
    PipelineUser,
    SourceScope,
)
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline
from app.services.observability.agent_execution_tracker import AgentExecutionTracker
from app.services.observability.log_safety import question_ref
from app.services.query.decomposer import DEFAULT_MAX_SUB_QUERIES
from app.services.security.rbac import Permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advanced-rag", tags=["advanced-rag"])


class AdvancedRAGRequest(BaseModel):
    """Request model for advanced RAG query."""

    query: str = Field(..., description="User query")
    session_id: str | None = Field(
        default=None,
        description="Session to persist this exchange into and to draw memory context from",
    )
    enable_decomposition: bool = Field(
        default=False,
        description="Enable query decomposition",
    )
    enable_self_rag: bool = Field(
        default=False,
        description="Enable Self-RAG evaluation",
    )
    approval_token: str | None = Field(
        default=None,
        min_length=24,
        max_length=256,
        description=(
            "Resume a run whose governed action was awaiting confirmation. Send the same "
            "query together with the token returned in `pending_approval`, after confirming "
            "it at POST /api/v1/connectors/approvals/{token}. The run replays the approved "
            "call rather than re-selecting a tool."
        ),
    )
    allowed_sources: list[str] | None = Field(
        default=None,
        description="Optional list of allowed sources",
    )
    use_web_fallback: bool = Field(
        default=False,
        description=(
            "Allow a freshness-driven web search on routes that did not ask for one. The web "
            "route searches the web regardless, and a caller with no documents falls back to it "
            "automatically unless WEB_SEARCH_ON_EMPTY_CORPUS is off."
        ),
    )
    timeout_ms: int | None = Field(
        default=None,
        ge=1_000,
        le=120_000,
        description=(
            "Stop spending time on this query after this many milliseconds. It narrows the "
            "server's own budget and never extends it, so a value above STAGE_TIMEOUT_TOTAL_MS "
            "has no effect. Relative rather than absolute on purpose: a client's clock does not "
            "have to agree with the server's. Scope resolution and output redaction still run."
        ),
    )


def _conversation_for(
    user: dict[str, Any],
    session_id: str | None,
    memory_context: str,
) -> tuple[ConversationMessage, ...]:
    """Carry the session as turns, with the resolved memory block ahead of them.

    `ConversationTurn` has always been a *sequence* of role/content pairs, but
    this endpoint collapsed the whole session into one `system` message holding a
    pre-rendered block. Synthesis could live with that -- it re-renders whatever
    it is given -- but query rewriting cannot: completing "它的成本呢？" into a
    standalone question means knowing what the previous turn asked, and a blob
    labelled `system` does not say.

    The block stays, ahead of the turns, because it also carries the long-term
    memories that the raw turns do not. Bounding stays with the consumers:
    `_render_conversation` caps what reaches synthesis, `SHORT_TERM_ROUNDS` caps
    what reaches rewriting.
    """
    turns: list[ConversationMessage] = []
    if memory_context:
        turns.append(ConversationMessage(role="system", content=memory_context))
    for question, answer in _recent_session_turns(user, session_id):
        turns.append(ConversationMessage(role="user", content=question))
        turns.append(ConversationMessage(role="assistant", content=answer))
    return tuple(turns)


def _deadline_from(timeout_ms: int | None) -> datetime | None:
    """Turn the client's relative budget into the absolute form the pipeline carries.

    The wire format is relative because the two clocks need not agree; the
    contract is absolute because the budget is consumed across stages and a
    relative value would have to be re-derived at each one.
    """
    if timeout_ms is None:
        return None
    return datetime.now(UTC) + timedelta(milliseconds=timeout_ms)


def _resolve_advanced_allowed_sources(
    user: dict[str, Any],
    requested_sources: list[str] | None,
) -> list[str]:
    visible_sources = _allowed_sources_for_user(user)
    if requested_sources is None:
        return visible_sources

    requested = {str(source or "").strip() for source in requested_sources if str(source or "").strip()}
    if not requested:
        return []
    return [source for source in visible_sources if source in requested]


def _decomposed_query_from_plan(query: str, plan_data: dict[str, Any] | None) -> DecomposedQuery | None:
    """Build a DecomposedQuery from the plan the pipeline actually ran, or None if it
    never decomposed (a single-task plan means decomposition didn't fire for this query)."""
    tasks = (plan_data or {}).get("tasks") or []
    sub_queries = [str(task.get("prompt", "")).strip() for task in tasks if str(task.get("prompt", "")).strip()]
    if len(sub_queries) <= 1:
        return None
    strategy = "sequential" if any(task.get("depends_on") for task in tasks) else "parallel"
    return DecomposedQuery(original_query=query, sub_queries=sub_queries[:4], decomposition_strategy=strategy)


def _context_docs(contexts: tuple[PipelineContext, ...]) -> list[dict[str, Any]]:
    return [
        {"id": ctx.document_id or ctx.chunk_id or ctx.source or "unknown", "content": ctx.content} for ctx in contexts
    ]


def _response_metadata(
    *,
    pipeline_result_metadata: dict[str, Any],
    route: str,
    citations: list[dict[str, Any]],
    tool_runs: list[dict[str, Any]],
    execution_id: str,
    session_id: str | None,
) -> dict[str, Any]:
    """Assemble the client-facing metadata block.

    ``execution_id`` is required by the SSE trace endpoint
    (``GET /api/v1/orchestration/executions/{execution_id}/events``); without it
    the client has no way to subscribe to the run it just started.
    """
    summary = retrieval_summary(pipeline_result_metadata)
    return {
        "route": route,
        "citations": citations,
        # Rides the same path citations do, so a multi-step run leaves a record
        # in the persisted message rather than only in the answer prose.
        "tool_runs": tool_runs,
        "validation": pipeline_result_metadata.get("validation", {}),
        # The badge read `web: no` on every answer because this block never
        # carried the field; the client defaulted a missing value to False.
        **summary,
        "execution_id": execution_id,
        "session_id": session_id,
    }


async def _persist_exchange(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    answer: str,
    metadata: dict[str, Any],
) -> None:
    """Write the user turn and the assistant turn into the session history.

    Mirrors the message-rerun path in ``app/api/routes/public/sessions.py`` so
    both entry points produce identically shaped history rows.  A persistence
    failure must never fail the request: the answer was already produced and
    returning it is strictly better than a 500.
    """
    if not session_id:
        return
    try:
        history_store = _history_store_for_user(user)
        history_store.append_message(session_id=session_id, role="user", content=question)
        history_store.append_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata=metadata,
        )
        _promote_long_term_memory(
            user=user,
            session_id=session_id,
            question=question,
            result={"answer": answer, **metadata},
        )
    except Exception:
        logger.exception("Failed to persist chat exchange for session %s", session_id)


async def _run_self_rag_evaluation(
    *,
    query: str,
    pipeline_result: PipelineResult,
    plan_data: dict[str, Any] | None,
) -> tuple[AnswerQuality | None, list[SubQueryResult]]:
    """Evaluate retrieval relevance and answer quality with the real SelfRAGEvaluator.

    Degrades to (None, []) on any failure so an evaluation problem never breaks the
    primary answer already produced by the pipeline.
    """
    try:
        from app.services.models.runtime import get_reasoning_model
        from app.services.retrieval.self_rag_evaluator import SelfRAGEvaluator

        docs = _context_docs(pipeline_result.contexts)
        llm_client = get_reasoning_model(temperature=0.0)
        evaluator = SelfRAGEvaluator(llm_client)

        relevance_scores = await evaluator.evaluate_retrieval_relevance(query, docs)
        answer_quality = await evaluator.evaluate_answer_quality(query, pipeline_result.answer, docs)

        sub_query_results: list[SubQueryResult] = []
        tasks = (plan_data or {}).get("tasks") or []
        if len(tasks) > 1:
            # Sub-queries share the evidence pool already retrieved for the primary
            # answer (no extra retrieval); relevance scores are reused across all of
            # them since evidence isn't tagged per-task by the retriever today.
            evidence_text = (
                "\n\n".join(f"[{doc['id']}] {doc['content'][:500]}" for doc in docs) or "(no evidence retrieved)"
            )
            for task in tasks:
                prompt = str(task.get("prompt", "")).strip()
                if not prompt:
                    continue
                try:
                    response = await llm_client.ainvoke(
                        "Answer this question using only the evidence below. If the evidence "
                        "does not cover it, say so briefly.\n\n"
                        f"Question: {prompt}\n\nEvidence:\n{evidence_text}"
                    )
                    answer_text = response.content if hasattr(response, "content") else str(response)
                except Exception:
                    logger.exception("Sub-query answer generation failed for task %s", task.get("task_id"))
                    answer_text = ""
                sub_query_results.append(
                    SubQueryResult(
                        sub_query=prompt,
                        documents=docs,
                        answer=answer_text,
                        relevance_scores=relevance_scores or None,
                    )
                )
        return answer_quality, sub_query_results
    except Exception:
        logger.exception("Self-RAG evaluation failed; returning primary answer without quality data")
        return None, []


def _retrieval_failure(exc: BaseException) -> RetrievalFailureError | None:
    """Find a `RetrievalFailureError` under whatever wrapped it.

    `run_with_timeout` re-raises every stage failure as `StageExecutionError`,
    keeping the original on `__cause__`, and LangGraph may wrap that again. A
    handler that matched only the bare type therefore never fired -- the first
    version of this fix did exactly that and still returned 500.
    """

    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, RetrievalFailureError):
            return exc
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return None


async def _process_advanced_rag_query_impl(
    request_data: AdvancedRAGRequest,
    request: Request,
    user: dict[str, Any],
):
    """
    Process query with advanced RAG techniques.

    This endpoint supports:
    - Query decomposition: Break complex queries into simpler sub-queries
    - Self-RAG: Evaluate retrieval relevance and answer quality

    Args:
        request_data: AdvancedRAGRequest with query and configuration

    Returns:
        AdvancedRAGResult with complete processing results
    """
    _require_permission(user, Permission.QUERY_RUN, request, "advanced-rag")

    session_id = _require_valid_session_id(request_data.session_id) if request_data.session_id else None

    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution(
        request_data.query,
        user_id=str(user.get("user_id", "") or "") or None,
        profile="advanced",
    )
    try:
        allowed_sources = _resolve_advanced_allowed_sources(user, request_data.allowed_sources)
        memory_context = _build_memory_context_for_session(user, session_id, request_data.query)
        conversation = _conversation_for(user, session_id, memory_context)
        pipeline_request = PipelineRequest(
            question=request_data.query,
            profile=PipelineProfile.ADVANCED,
            session_id=session_id,
            conversation=conversation,
            user=PipelineUser(
                user_id=str(user.get("user_id", "") or "") or None,
                username=str(user.get("username", "") or "") or None,
                role=str(user.get("role", "") or "") or None,
                permissions=frozenset(user.get("permissions") or []),
            ),
            source_scope=SourceScope(allowed_sources=frozenset(allowed_sources)),
            enable_decomposition=request_data.enable_decomposition,
            enable_self_rag=request_data.enable_self_rag,
            approval_token=request_data.approval_token,
            use_web_fallback=request_data.use_web_fallback,
            deadline_at=_deadline_from(request_data.timeout_ms),
            execution_id=execution_id,
        )
        pipeline_result = await RAGPipeline().execute(pipeline_request)
        plan_data = pipeline_result.execution_metadata.get("plan")

        decomposed_query = (
            _decomposed_query_from_plan(request_data.query, plan_data) if request_data.enable_decomposition else None
        )

        answer_quality = None
        sub_query_results: list[SubQueryResult] = []
        if request_data.enable_self_rag:
            answer_quality, sub_query_results = await _run_self_rag_evaluation(
                query=request_data.query,
                pipeline_result=pipeline_result,
                plan_data=plan_data,
            )

        # Rides the request's own metrics row, which is the window build_ops_alerts
        # already reads for its p95 -- see record_grounding_support.
        record_grounding_support(request, pipeline_result.execution_metadata)
        metadata = _response_metadata(
            pipeline_result_metadata=dict(pipeline_result.execution_metadata),
            route=pipeline_result.route.route,
            citations=[citation.model_dump(mode="json") for citation in pipeline_result.citations],
            tool_runs=[run.model_dump(mode="json") for run in pipeline_result.tool_runs],
            execution_id=execution_id,
            session_id=session_id,
        )
        await _persist_exchange(
            user=user,
            session_id=session_id,
            question=request_data.query,
            answer=pipeline_result.answer,
            metadata=metadata,
        )

        result = AdvancedRAGResult(
            query=request_data.query,
            decomposed_query=decomposed_query,
            sub_query_results=sub_query_results,
            final_answer=pipeline_result.answer,
            # 200 with a discriminator rather than 202: the run completed and the
            # answer is the answer. Only the governed action is outstanding, so a
            # client that ignores these two fields still behaves correctly.
            status=pipeline_result.status,
            pending_approval=(
                None
                if pipeline_result.pending_approval is None
                else PendingApprovalView(**pipeline_result.pending_approval.model_dump())
            ),
            answer_quality=answer_quality,
            metadata=metadata,
        )
        tracker.complete_execution(execution_id, result.model_dump())
        return result
    except Exception as exc:
        retrieval_failure = _retrieval_failure(exc)
        if retrieval_failure is None:
            tracker.fail_execution(execution_id, str(exc))
            logger.exception("Error processing advanced RAG query")
            raise internal_error("Unable to process advanced query") from exc

        # Every retriever that ran, failed. That is a dependency being down --
        # most often the web search, which is the *only* source when the caller
        # has no documents -- not a defect in this service, and answering it with
        # a bare 500 threw away the one thing the caller could act on. A closely
        # related case was fixed once already: a caller with an empty corpus had
        # every document source counted as failed, and their first question
        # surfaced as a 500 (see `RAGAgentService.retrieve`). This is the other
        # half of it.
        tracker.fail_execution(execution_id, str(exc))
        failed = ", ".join(sorted(retrieval_failure.failed_retrievers)) or "unknown"
        logger.warning("Retrieval failed for every source (%s) on %s", failed, question_ref(request_data.query))
        raise service_unavailable(
            f"No evidence could be retrieved: every source failed ({failed}). "
            "This is usually a transient upstream failure; retrying often works."
        ) from exc


@router.post("/query", response_model=AdvancedRAGResult)
async def process_advanced_rag_query(
    request_data: AdvancedRAGRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    async with _reserve_chat_credit_async(request, user, "advanced_query") as credit:
        response = await _process_advanced_rag_query_impl(request_data, request, user)
        credit.commit()
        return response


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "advanced-rag",
        "features": {
            "query_decomposition": True,
            "self_rag": True,
        },
    }


@router.get("/config", dependencies=[Depends(require_admin)])
async def get_config():
    """Report the switches that actually gate these two features.

    Every value here used to come from an environment variable that nothing else
    reads: `ENABLE_QUERY_DECOMPOSITION` against a real switch named
    `QUERY_DECOMPOSE_ENABLED` that defaults to *on*, so the page said "false"
    while the feature ran; `ENABLE_SELF_RAG` against a gate that lives on
    `VectorRAGConfig`; and a `max_sub_queries` unrelated to the bound the
    decomposer enforces. A configuration page that reports something other than
    the running configuration is worse than no page.
    """

    settings = get_settings()
    return {
        "query_decomposition": {
            "enabled_by_default": settings.query_decompose_enabled,
            "max_sub_queries": DEFAULT_MAX_SUB_QUERIES,
        },
        "self_rag": {
            "enabled_by_default": get_vector_rag_config().enable_evaluation,
            "relevance_threshold": settings.self_rag_relevance_threshold,
            "quality_threshold": settings.self_rag_quality_threshold,
        },
    }
