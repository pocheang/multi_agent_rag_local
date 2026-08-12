"""Typed construction and finalization data for public query responses."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.api.dependencies import settings
from app.api.schemas import Citation, QueryResponse
from app.services.observability.agent_execution_tracker import AgentExecutionTracker
from app.services.observability.alerting import resolve_signing_secret, sign_payload
from app.services.evidence_conflict import detect_evidence_conflict
from app.services.runtime.rag_runtime_scope import execution_route_from_result


@dataclass(frozen=True)
class PreparedQueryResponse:
    """Response plus the side-effect data consumed by the request handler."""

    response: QueryResponse
    history_metadata: dict[str, Any]
    grounding_support: float


def build_query_response(
    *,
    answer: str,
    route: str,
    citations: Sequence[Citation],
    graph_entities: Sequence[str] = (),
    web_used: bool = False,
    detected_language: str = "zh",
    execution_id: str | None = None,
    debug: Mapping[str, Any] | None = None,
) -> QueryResponse:
    """Build the public response shared by query compatibility paths."""
    return QueryResponse(
        answer=answer,
        route=route,
        citations=list(citations),
        graph_entities=list(graph_entities),
        web_used=web_used,
        detected_language=detected_language,
        execution_id=execution_id,
        debug=dict(debug or {}),
    )


def parse_query_response(payload: Mapping[str, Any]) -> QueryResponse:
    """Validate a cached compatibility payload at the response boundary."""
    return QueryResponse.model_validate(payload)


def ensure_trackable_execution_result(
    result: dict[str, Any],
    *,
    question: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    """Ensure cached responses still point to a live execution trace."""
    payload = dict(result or {})
    tracker = AgentExecutionTracker.get_instance()
    execution_id = str(payload.get("execution_id", "") or "").strip()
    if execution_id and tracker.get_execution_trace(execution_id) is not None:
        return payload

    execution_id = tracker.start_execution(
        question,
        user_id=str(user.get("user_id", "") or "") or None,
        profile="standard",
    )
    payload["execution_id"] = execution_id
    tracker.complete_execution(execution_id, payload)
    return payload


def maybe_sign_response(
    payload: dict[str, Any],
    *,
    user: dict[str, Any],
    session_id: str,
    question: str,
) -> tuple[str | None, str | None]:
    """Attach an optional HMAC signature to response metadata."""
    if not bool(getattr(settings, "response_signing_enabled", True)):
        return None, None
    kid, secret = resolve_signing_secret()
    if not kid or not secret:
        return None, None
    signed_payload = {
        "payload": payload,
        "user_id": str(user.get("user_id", "") or ""),
        "session_id": str(session_id or ""),
        "question": str(question or ""),
    }
    return sign_payload(signed_payload, secret), kid


def prepare_query_response(
    *,
    result: dict[str, Any],
    consistency_info: dict[str, Any],
    request_trace_id: str,
    user: dict[str, Any],
    session_id: str | None,
    effective_question: str,
    requested_use_reasoning: bool,
    effective_use_reasoning: bool,
    is_fast_smalltalk: bool,
    retrieval_strategy: str | None,
    strategy_meta: Mapping[str, Any],
) -> PreparedQueryResponse:
    """Normalize a workflow payload without performing persistence side effects."""
    vector_result = result.get("vector_result", {})
    web_result = result.get("web_result", {})
    graph_result = result.get("graph_result", {})
    vector_citations_raw = vector_result.get("citations", [])
    web_citations_raw = web_result.get("citations", [])
    vector_citations = [Citation(**item) for item in vector_citations_raw]
    web_citations = [Citation(**item) for item in web_citations_raw]
    conflict_report = detect_evidence_conflict(vector_citations_raw + web_citations_raw)

    if conflict_report.get("conflict"):
        warning = (
            "⚠️ 注意：检索到的信息中存在相互矛盾的内容，以下回答已综合考虑多方观点。\n\n"
            if result.get("detected_language", "zh") == "zh"
            else "⚠️ Note: Conflicting information was found in the retrieved sources. "
            "The answer below considers multiple perspectives.\n\n"
        )
        result["answer"] = f"{warning}{result.get('answer', '')}"

    execution_route = execution_route_from_result(result)
    debug: dict[str, Any] = {
        "reason": result.get("reason", ""),
        "skill": result.get("skill", ""),
        "agent_class": result.get("agent_class", "general"),
        "execution_route": execution_route,
        "vector_retrieved": vector_result.get("retrieved_count", 0),
        "vector_effective_hits": vector_result.get("effective_hit_count", 0),
        "retrieval_diagnostics": vector_result.get("retrieval_diagnostics", {}),
        "grounding": result.get("grounding", {}),
        "answer_safety": result.get("answer_safety", {}),
        "explainability": result.get("explainability", {}),
        "consistency": consistency_info,
        "use_reasoning": effective_use_reasoning,
        "requested_use_reasoning": requested_use_reasoning,
        "fast_smalltalk_path": is_fast_smalltalk,
        "retrieval_strategy": retrieval_strategy or "advanced",
        "retrieval_strategy_reason": strategy_meta.get("reason"),
        "retrieval_strategy_bucket": strategy_meta.get("bucket"),
        "evidence_conflict": conflict_report,
        "source_scope": result.get("source_scope", {}),
        "trace_id": request_trace_id,
    }
    signature, signature_kid = maybe_sign_response(
        {"answer": result.get("answer", ""), "route": result.get("route", "unknown"), "trace_id": request_trace_id},
        user=user,
        session_id=str(session_id or ""),
        question=effective_question,
    )
    if signature:
        debug["signature"] = signature
        debug["signature_kid"] = signature_kid

    response = build_query_response(
        answer=str(result.get("answer", "")),
        route=str(result.get("route", "unknown")),
        citations=vector_citations + web_citations,
        graph_entities=graph_result.get("entities", []),
        web_used=bool(web_result.get("used", False)),
        detected_language=str(result.get("detected_language", "zh")),
        execution_id=result.get("execution_id"),
        debug=debug,
    )
    history_metadata = {
        "route": result.get("route", "unknown"),
        "execution_route": execution_route,
        "agent_class": result.get("agent_class", "general"),
        "web_used": web_result.get("used", False),
        "thoughts": result.get("thoughts", []),
        "graph_entities": graph_result.get("entities", []),
        "citations": vector_citations_raw + web_citations_raw,
        "retrieval_diagnostics": vector_result.get("retrieval_diagnostics", {}),
        "grounding": result.get("grounding", {}),
        "explainability": result.get("explainability", {}),
        "answer_safety": result.get("answer_safety", {}),
        "consistency": consistency_info,
        "evidence_conflict": conflict_report,
        "source_scope": result.get("source_scope", {}),
    }
    grounding_support = float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0)
    return PreparedQueryResponse(response=response, history_metadata=history_metadata, grounding_support=grounding_support)


__all__ = [
    "PreparedQueryResponse",
    "build_query_response",
    "ensure_trackable_execution_result",
    "maybe_sign_response",
    "parse_query_response",
    "prepare_query_response",
]


