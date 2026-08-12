"""Standard-profile preparation owned by orchestration.

The pipeline supplies an immutable public request and delegates it here.  This
module owns the retained request decisions before compatibility execution:
visible-source scope, PDF targeting, smalltalk degradation, session strategy
locks, and memory context.  It deliberately imports neither HTTP nor pipeline
contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.domain.text import normalize_string
from app.orchestration.request import ConversationTurn, OrchestrationRequest, RequestScope
from app.services.agent_classifier import classify_agent_class
from app.services.sessions.history import HistoryStore
from app.services.documents.index_manager import list_indexed_files
from app.services.input_normalizer import enhance_user_question_for_completion
from app.services.sessions.memory_store import MemoryStore, build_memory_context
from app.services.pdf_agent_guard import (
    apply_pdf_focus_to_question,
    build_choose_pdf_hint,
    build_upload_pdf_hint,
    choose_pdf_targets,
)
from app.services.query_intent import is_casual_chat_query
from app.services.runtime.rag_runtime_scope import is_under_path
from app.services.retrieval.profiles import normalize_retrieval_profile, profile_force_local_only, profile_to_strategy
from app.services.runtime.runtime_ops import resolve_profile_for_request

_SETTINGS = get_settings()
_ALLOWED_AGENT_CLASSES = {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"}


def normalize_agent_class_hint(value: str | None) -> str | None:
    """Normalize a public agent-class hint under the standard request policy."""
    hint = normalize_string(value, lowercase=True)
    return hint if hint in _ALLOWED_AGENT_CLASSES else None


def resolve_effective_agent_class(question: str, agent_class_hint: str | None) -> str:
    """Resolve the canonical agent class for a standard request or API compatibility caller."""
    hinted = normalize_agent_class_hint(agent_class_hint)
    if hinted:
        return hinted
    guessed = classify_agent_class(question)
    return guessed if guessed in _ALLOWED_AGENT_CLASSES else "general"


def normalize_retrieval_strategy(value: str | None) -> str:
    """Normalize a public retrieval strategy under the standard request policy."""
    strategy = normalize_string(value, lowercase=True)
    return normalize_retrieval_profile(strategy if strategy in {"baseline", "advanced", "safe"} else None)


def effective_strategy_for_session(
    *,
    req_strategy: str | None,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    history_store_fn: Callable[[dict[str, Any]], HistoryStore],
) -> tuple[str, dict[str, Any]]:
    """Resolve the request profile while honoring an existing session strategy lock."""
    if req_strategy is not None:
        requested = normalize_retrieval_strategy(req_strategy)
        return resolve_profile_for_request(
            requested,
            user_id=str(user.get("user_id", "")),
            session_id=str(session_id or ""),
            question=question,
        )
    lock = history_store_fn(user).get_session_strategy_lock(session_id) if session_id else None
    if lock:
        return normalize_retrieval_profile(lock), {"reason": "session_lock", "bucket": None}
    return resolve_profile_for_request(
        None,
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=question,
    )


@dataclass(frozen=True)
class EarlyStandardResponse:
    """An engine-owned policy result with the legacy response metadata."""

    answer: str
    route: str
    reason: str
    skill: str
    agent_class: str


@dataclass(frozen=True)
class PreparedStandardRequest:
    """The resolved orchestration request and public-response compatibility data."""

    request: OrchestrationRequest
    original_question: str
    effective_question: str
    allowed_sources: list[str]
    retrieval_strategy: str
    strategy_meta: dict[str, Any]
    is_fast_smalltalk: bool
    effective_use_reasoning: bool
    early_response: EarlyStandardResponse | None = None


@dataclass(frozen=True)
class StandardExecutionContext:
    """Request-scoped runtime ports consumed by the compatibility executor."""

    user: dict[str, Any]
    session_id: str | None
    original_question: str
    is_fast_smalltalk: bool
    overload_mode: bool
    latest_answer: Callable[[], str | None]
    shadow_queue: object | None = None
    source_scope_audit: Callable[[str, str], None] | None = None
    result_signer: Callable[[dict[str, Any]], tuple[str | None, str | None]] | None = None
    trace_id: str = ""
    early_response: EarlyStandardResponse | None = None


def _user_mapping(request: OrchestrationRequest) -> dict[str, Any]:
    actor = request.actor
    if actor is None or not actor.user_id:
        return {"user_id": "anonymous", "role": "viewer"}
    return {"user_id": actor.user_id, "username": actor.username or "", "role": actor.role or "viewer"}


def _history_store(user: dict[str, Any]) -> HistoryStore:
    return HistoryStore(base_dir=_SETTINGS.sessions_path / str(user["user_id"]))


def _visible_documents(user: dict[str, Any]) -> list[dict[str, Any]]:
    user_root = (_SETTINGS.uploads_path / str(user["user_id"])).resolve()
    docs_root = _SETTINGS.docs_path.resolve()
    user_id = str(user["user_id"])
    visible: list[dict[str, Any]] = []
    for row in list_indexed_files():
        source = str(row.get("source", "") or "")
        if not source:
            continue
        source_path = Path(source).resolve()
        if is_under_path(source_path, docs_root):
            visible.append(row)
            continue
        if str(row.get("visibility", "private") or "private").lower() == "public":
            visible.append(row)
            continue
        if str(row.get("owner_user_id", "") or "") == user_id or user_root in source_path.parents:
            visible.append(row)
    return visible


def _allowed_sources(user: dict[str, Any], filenames: list[str] | None = None) -> list[str]:
    wanted = set(filenames or ())
    allowed: list[str] = []
    for row in _visible_documents(user):
        if wanted and str(row.get("filename", "") or "") not in wanted:
            continue
        source = str(row.get("source", "") or "").strip()
        if source and source not in allowed:
            allowed.append(source)
    return allowed


def _effective_agent_class(question: str, hint: str | None) -> str:
    return resolve_effective_agent_class(question, hint)


def _pdf_preparation(
    question: str, user: dict[str, Any]
) -> tuple[str | None, list[str] | None, EarlyStandardResponse | None]:
    pdf_names: list[str] = []
    chunks_by_name: dict[str, int] = {}
    for row in _visible_documents(user):
        filename = str(row.get("filename", "") or "").strip()
        if Path(filename).suffix.lower() not in {
            ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp",
        }:
            continue
        if filename and filename not in pdf_names:
            pdf_names.append(filename)
        try:
            chunks_by_name[filename] = max(chunks_by_name.get(filename, 0), int(row.get("chunks", 0) or 0))
        except (TypeError, ValueError):
            chunks_by_name.setdefault(filename, 0)
    if not pdf_names:
        return None, None, EarlyStandardResponse(
            answer=build_upload_pdf_hint(), route="pdf_text", reason="pdf_agent_no_pdf",
            skill="pdf_text_reader", agent_class="pdf_text",
        )
    selected = choose_pdf_targets(question, pdf_names)
    if len(pdf_names) > 1 and not selected:
        return None, None, EarlyStandardResponse(
            answer=build_choose_pdf_hint(pdf_names), route="pdf_text", reason="pdf_agent_need_selection",
            skill="pdf_text_reader", agent_class="pdf_text",
        )
    if selected:
        selected_with_chunks = [name for name in selected if chunks_by_name.get(name, 0) > 0]
        if not selected_with_chunks:
            return None, None, EarlyStandardResponse(
                answer=(
                    "The selected document exists, but its index is empty (chunks=0), so I cannot read detailed content yet.\n"
                    "Please click Reindex for this file, then ask again."
                ),
                route="pdf_text", reason="pdf_agent_chunks_zero", skill="pdf_text_reader", agent_class="pdf_text",
            )
        return apply_pdf_focus_to_question(question, selected_with_chunks), _allowed_sources(user, selected_with_chunks), None
    return question, None, None


def _memory_context(user: dict[str, Any], session_id: str | None, question: str) -> str:
    if not session_id:
        return ""
    session = _history_store(user).get_session(session_id) or {}
    long_term = MemoryStore(base_dir=_SETTINGS.sessions_path / str(user["user_id"]) / "_long_memory").list_long_term(
        session_id
    )
    return build_memory_context(
        question=question, session_messages=session.get("messages", []) or [], long_term_memories=long_term
    )


def _strategy(
    user: dict[str, Any], session_id: str | None, question: str, requested: str | None
) -> tuple[str, dict[str, Any]]:
    return effective_strategy_for_session(
        req_strategy=requested,
        user=user,
        session_id=session_id,
        question=question,
        history_store_fn=_history_store,
    )


def prepare_standard_request(request: OrchestrationRequest) -> PreparedStandardRequest:
    """Resolve the retained standard-profile policy before compatibility execution."""
    if request.profile != "standard":
        raise ValueError("standard request preparation requires the standard profile")
    user = _user_mapping(request)
    original_question = request.question
    agent_class = _effective_agent_class(original_question, request.source_scope.agent_class_hint)
    if (
        "æ–‡ä»¶" in original_question or "æ–‡æ¡£" in original_question or "pdf" in original_question.lower()
        or "èµ„æ–™" in original_question or "ä¸Šä¼ " in original_question
    ):
        inventory_terms = ("å‡ ä¸ª", "å¤šå°‘", "æ•°é‡", "æœ‰å“ªäº›", "åˆ—è¡¨", "æ¸…å•", "åˆ—å‡º", "å¤šå°‘ä¸ª")
        if any(term in original_question.lower() for term in inventory_terms):
            names = [str(row.get("filename", "") or "").strip() for row in _visible_documents(user)]
            names = [name for index, name in enumerate(names) if name and name not in names[:index]]
            answer = (
                "ä½ å½“å‰å¯è®¿é—®çš„æ–‡ä»¶æ•°é‡ä¸º 0ã€‚"
                if not names else f"ä½ å½“å‰å¯è®¿é—®çš„æ–‡ä»¶å…± {len(names)} ä¸ªï¼š{'ã€'.join(names[:20])}{f'ï¼ˆå…¶ä½™ {len(names) - 20} ä¸ªå·²çœç•¥ï¼‰' if len(names) > 20 else ''}ã€‚"
            )
            return PreparedStandardRequest(request, original_question, original_question, [], "advanced", {}, False, False,
                EarlyStandardResponse(answer, "policy", "user_file_inventory_only", "policy_guard", "policy"))
    question = original_question
    selected_sources: list[str] | None = None
    if agent_class == "pdf_text":
        question, selected_sources, early = _pdf_preparation(question, user)
        if early is not None:
            return PreparedStandardRequest(request, original_question, original_question, [], "advanced", {}, False,
                bool(request.use_reasoning), early)
        question = question or original_question
    smalltalk = is_casual_chat_query(question)
    effective_question = question if smalltalk else enhance_user_question_for_completion(question)
    strategy, strategy_meta = _strategy(user, request.session_id, effective_question, request.retrieval_strategy)
    use_web = bool(request.use_web_fallback and not profile_force_local_only(strategy))
    use_reasoning = bool(request.use_reasoning)
    if smalltalk:
        use_web, use_reasoning, strategy, strategy_meta = False, False, "baseline", {"reason": "smalltalk_fast_path", "bucket": "smalltalk"}
    allowed_sources = selected_sources if selected_sources is not None else _allowed_sources(user)
    resolved_hint = str(request.source_scope.agent_class_hint or "").strip().lower()
    resolved_hint = resolved_hint if resolved_hint in _ALLOWED_AGENT_CLASSES else None
    execution_strategy = profile_to_strategy(strategy) if (request.retrieval_strategy is not None or strategy != "advanced") else None
    memory_context = "" if smalltalk else _memory_context(user, request.session_id, effective_question)
    resolved = request.model_copy(update={
        "question": effective_question,
        "conversation": (ConversationTurn(role="system", content=memory_context),) if memory_context else tuple(),
        "source_scope": RequestScope(allowed_sources=frozenset(allowed_sources), agent_class_hint=resolved_hint),
        "retrieval_strategy": execution_strategy,
        "use_web_fallback": use_web,
        "use_reasoning": use_reasoning,
    })
    return PreparedStandardRequest(resolved, original_question, effective_question, allowed_sources, strategy, strategy_meta,
        smalltalk, use_reasoning)


def bind_standard_runtime_context(
    prepared: PreparedStandardRequest,
    *,
    user: dict[str, Any] | None = None,
    overload_mode: bool = False,
    latest_answer: Callable[[], str | None] | None = None,
    shadow_queue: object | None = None,
    source_scope_audit: Callable[[str, str], None] | None = None,
    result_signer: Callable[[dict[str, Any]], tuple[str | None, str | None]] | None = None,
    trace_id: str = "",
) -> PreparedStandardRequest:
    """Attach host callbacks without making HTTP code own execution policy."""
    runtime = StandardExecutionContext(
        user=dict(user or _user_mapping(prepared.request)),
        session_id=prepared.request.session_id,
        original_question=prepared.original_question,
        is_fast_smalltalk=prepared.is_fast_smalltalk,
        overload_mode=overload_mode,
        latest_answer=latest_answer or (lambda: None),
        shadow_queue=shadow_queue,
        source_scope_audit=source_scope_audit,
        result_signer=result_signer,
        trace_id=trace_id,
        early_response=prepared.early_response,
    )
    return replace(prepared, request=prepared.request.model_copy(update={"runtime_context": runtime}))


__all__ = [
    "EarlyStandardResponse", "PreparedStandardRequest", "StandardExecutionContext",
    "bind_standard_runtime_context", "prepare_standard_request",
]
