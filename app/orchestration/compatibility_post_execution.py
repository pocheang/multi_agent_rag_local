"""Post-execution policy for retained standard-profile compatibility flows.

The public pipeline translates request contracts only.  This module owns the
legacy execution follow-up policy, including stream terminal shaping, so the
same compatibility executor remains the single owner of those semantics.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.orchestration.standard_request_policy import StandardExecutionContext
from app.services.consistency_guard import should_stabilize, text_similarity
from app.services.evidence_conflict import detect_evidence_conflict
from app.services.legacy_synthesis import synthesize_answer
from app.services.runtime.rag_runtime_scope import execution_route_from_result


class CompatibilitySourceScope(Protocol):
    """The source filter fields required by retained standard-profile policy."""

    allowed_sources: frozenset[str] | None


class CompatibilityRequest(Protocol):
    """Structural request contract that avoids an orchestration-to-pipeline import."""

    question: str
    source_scope: CompatibilitySourceScope
    use_web_fallback: bool
    use_reasoning: bool
    retrieval_strategy: str | None

    def model_copy(self, *, update: dict[str, Any]) -> CompatibilityRequest:
        """Return a copy with the compatibility fallback overrides applied."""


SourceScopeEnforcer = Callable[[dict[str, Any], list[str] | None], dict[str, Any]]
ResultResynthesizer = Callable[[dict[str, Any], str, str, bool], dict[str, Any]]
ResultSigner = Callable[[dict[str, Any]], tuple[str | None, str | None]]
ShadowSubmitter = Callable[[dict[str, Any], CompatibilityRequest], dict[str, Any]]
SourceScopeAudit = Callable[[str, str], None]


def _vector_context_from_citations(citations: list[dict[str, Any]]) -> str:
    """Rebuild the legacy synthesis context from citations retained by scope."""
    blocks: list[str] = []
    for citation in citations:
        metadata = citation.get("metadata", {}) or {}
        source = str(citation.get("source", "") or Path(str(metadata.get("source", "") or "unknown")).name)
        retrieval_sources = metadata.get("retrieval_sources", [])
        if not isinstance(retrieval_sources, list):
            retrieval_sources = [str(retrieval_sources)]
        retrieval_label = ",".join(str(item) for item in retrieval_sources if str(item).strip()) or "filtered"
        blocks.append(
            f"[SOURCE: {source or 'unknown'}]\\n[RETRIEVAL: {retrieval_label}]\\n"
            f"{str(citation.get('content', '') or '')}"
        )
    return "\\n\\n".join(blocks)


def enforce_result_source_scope(
    result: dict[str, Any],
    allowed_sources: list[str] | None,
    *,
    audit: SourceScopeAudit | None = None,
) -> dict[str, Any]:
    """Apply the established source filter without importing the HTTP layer."""
    allowed_set = set(allowed_sources or ())
    source_scope = dict(result.get("source_scope", {}) or {})
    if not allowed_set:
        vector_result = dict(result.get("vector_result", {}) or {})
        denied = len(list(vector_result.get("citations", []) or []))
        vector_result.update({"citations": [], "context": "", "retrieved_count": 0, "effective_hit_count": 0})
        graph_result = dict(result.get("graph_result", {}) or {})
        graph_filtered = bool(
            graph_result.get("context")
            or graph_result.get("entities")
            or graph_result.get("neighbors")
            or graph_result.get("paths")
        )
        if graph_filtered:
            graph_result.update({"context": "", "entities": [], "neighbors": [], "paths": []})
        source_scope.update(
            {
                "checked": True,
                "allowed_source_count": 0,
                "filtered_vector_citations": denied,
                "filtered_graph": graph_filtered,
            }
        )
        out = dict(result)
        out.update({"vector_result": vector_result, "graph_result": graph_result, "source_scope": source_scope})
        if audit is not None:
            audit("denied", f"no_allowed_sources; filtered_citations={denied}")
        return out

    vector_result = dict(result.get("vector_result", {}) or {})
    citations = list(vector_result.get("citations", []) or [])
    kept: list[dict[str, Any]] = []
    denied = 0
    for citation in citations:
        metadata = citation.get("metadata", {}) or {}
        source = str(metadata.get("source", "") or "")
        if source and source in allowed_set:
            kept.append(citation)
        else:
            denied += 1
    if audit is not None:
        audit(
            "denied" if denied else "success",
            f"filtered_citations={denied}" if denied else f"citations_checked={len(citations)}",
        )
    vector_result["citations"] = kept
    vector_result["retrieved_count"] = len(kept)
    vector_result["effective_hit_count"] = min(int(vector_result.get("effective_hit_count", len(kept)) or 0), len(kept))
    vector_result["context"] = _vector_context_from_citations(kept)
    source_scope.update(
        {
            "checked": True,
            "allowed_source_count": len(allowed_set),
            "filtered_vector_citations": denied,
            "filtered_graph": False,
        }
    )
    out = dict(result)
    out.update({"vector_result": vector_result, "source_scope": source_scope})
    return out


def resynthesize_after_source_scope(
    result: dict[str, Any], *, question: str, memory_context: str, use_reasoning: bool
) -> dict[str, Any]:
    """Preserve the legacy single resynthesis step after scope filtering."""
    scope = result.get("source_scope", {}) or {}
    if not bool(scope.get("filtered_vector_citations", 0) or scope.get("filtered_graph", False)):
        return result
    answer = synthesize_answer(
        question=question,
        skill_name=str(result.get("skill", "") or "answer_with_citations"),
        memory_context=memory_context,
        vector_context=str((result.get("vector_result", {}) or {}).get("context", "") or ""),
        graph_context=str((result.get("graph_result", {}) or {}).get("context", "") or ""),
        web_context=str((result.get("web_result", {}) or {}).get("context", "") or ""),
        use_reasoning=use_reasoning,
    )
    out = dict(result)
    out["answer"] = answer["answer"] if isinstance(answer, dict) else answer
    out["detected_language"] = answer.get("detected_language", "zh") if isinstance(answer, dict) else "zh"
    source_scope = dict(out.get("source_scope", {}) or {})
    source_scope["answer_resynthesized"] = True
    out["source_scope"] = source_scope
    return out


@dataclass(frozen=True)
class StandardPostExecutionServices:
    """Host callbacks for request-scoped legacy policy and telemetry."""

    is_overload_mode: Callable[[], bool]
    enforce_source_scope: SourceScopeEnforcer
    resynthesize: ResultResynthesizer
    latest_answer: Callable[[], str | None]
    shadow_submit: ShadowSubmitter
    consistency_enabled: bool
    consistency_threshold: float


def build_standard_post_execution_services(
    context: StandardExecutionContext,
    *,
    shadow_submit: ShadowSubmitter,
) -> StandardPostExecutionServices:
    """Bind explicit runtime ports without importing HTTP-layer helpers."""
    settings = get_settings()

    return StandardPostExecutionServices(
        is_overload_mode=lambda: context.overload_mode,
        enforce_source_scope=lambda result, scoped_sources: enforce_result_source_scope(
            result, scoped_sources, audit=context.source_scope_audit
        ),
        resynthesize=lambda result, question, memory_context, use_reasoning: resynthesize_after_source_scope(
            result, question=question, memory_context=memory_context, use_reasoning=use_reasoning
        ),
        latest_answer=context.latest_answer,
        shadow_submit=shadow_submit,
        consistency_enabled=bool(settings.consistency_guard_enabled),
        consistency_threshold=float(settings.consistency_guard_similarity_threshold),
    )


async def execute_standard_compatibility(
    *,
    execute_profile: Callable[[CompatibilityRequest], Awaitable[dict[str, Any]]],
    request: CompatibilityRequest,
    original_question: str,
    memory_context: str,
    is_fast_smalltalk: bool,
    services: StandardPostExecutionServices,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the established standard-profile fallback, filtering, and retry."""

    runtime_request = request
    if services.is_overload_mode():
        runtime_request = request.model_copy(
            update={
                "use_web_fallback": False,
                "use_reasoning": False,
                "retrieval_strategy": request.retrieval_strategy or "baseline",
            }
        )

    async def execute_once_async(current_request: CompatibilityRequest) -> dict[str, Any]:
        payload = services.shadow_submit(await execute_profile(current_request), current_request)
        filtered = services.enforce_source_scope(payload, list(current_request.source_scope.allowed_sources or ()))
        return services.resynthesize(
            filtered,
            current_request.question,
            memory_context,
            current_request.use_reasoning,
        )

    result = await execute_once_async(runtime_request)
    consistency = {"checked": False}
    if not services.consistency_enabled or is_fast_smalltalk:
        return result, consistency

    previous_answer = services.latest_answer()
    if not previous_answer:
        return result, consistency

    similarity = text_similarity(previous_answer, result.get("answer", ""))
    consistency = {
        "checked": True,
        "previous_similarity": round(similarity, 4),
        "stabilized": False,
    }
    if not should_stabilize(
        previous_answer=previous_answer,
        new_answer=result.get("answer", ""),
        threshold=services.consistency_threshold,
    ):
        return result, consistency

    retried = await execute_once_async(
        runtime_request.model_copy(update={"retrieval_strategy": "baseline", "use_reasoning": False})
    )
    retried_similarity = text_similarity(previous_answer, retried.get("answer", ""))
    if retried_similarity > similarity:
        return retried, {
            "checked": True,
            "previous_similarity": round(similarity, 4),
            "retried_similarity": round(retried_similarity, 4),
            "stabilized": True,
        }
    return result, consistency


@dataclass(frozen=True)
class StreamPostExecutionContext:
    """Values that affect the legacy terminal stream result."""

    allowed_sources: list[str] | None
    question: str
    memory_context: str
    use_reasoning: bool
    retrieval_strategy: str | None
    trace_id: str


@dataclass(frozen=True)
class StreamResultPostProcessor:
    """Apply established terminal shaping before emitting a public SSE event."""

    context: StreamPostExecutionContext
    sign_result: ResultSigner
    audit_source_scope: SourceScopeAudit | None = None
    enforce_source_scope: SourceScopeEnforcer | None = None
    resynthesize: ResultResynthesizer | None = None

    def with_use_reasoning(self, use_reasoning: bool) -> StreamResultPostProcessor:
        """Bind legacy overload fallback before processing the terminal event."""
        return replace(self, context=replace(self.context, use_reasoning=use_reasoning))

    def finalize(self, result: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        """Return the final payload and an SSE reset only for real resynthesis.

        The historical stream handler saved the answer *after* source-scope
        enforcement, then emitted ``answer_reset`` only if resynthesis changed
        that scoped answer.  Conflict-warning decoration remains terminal
        shaping and must never independently create a reset event.
        """
        enforcer = self.enforce_source_scope or (
            lambda payload, sources: enforce_result_source_scope(payload, sources, audit=self.audit_source_scope)
        )
        resynthesizer = self.resynthesize or (
            lambda payload, question, memory_context, use_reasoning: resynthesize_after_source_scope(
                payload,
                question=question,
                memory_context=memory_context,
                use_reasoning=use_reasoning,
            )
        )
        final_result = enforcer(result, self.context.allowed_sources)
        original_stream_answer = str(final_result.get("answer", "") or "")
        final_result = resynthesizer(
            final_result,
            self.context.question,
            self.context.memory_context,
            self.context.use_reasoning,
        )
        reset_content = (
            str(final_result.get("answer", "") or "")
            if str(final_result.get("answer", "") or "") != original_stream_answer
            else None
        )
        citations = list(final_result.get("vector_result", {}).get("citations", []) or [])
        citations += list(final_result.get("web_result", {}).get("citations", []) or [])
        conflict_report = detect_evidence_conflict(citations)
        final_result["evidence_conflict"] = conflict_report
        if conflict_report.get("conflict"):
            final_result["answer"] = f"[evidence-conflict-warning]\n{final_result.get('answer', '')}"
        final_result["execution_route"] = execution_route_from_result(final_result)
        final_result["retrieval_strategy"] = self.context.retrieval_strategy or "advanced"
        final_result["trace_id"] = self.context.trace_id
        signature, signature_kid = self.sign_result(final_result)
        if signature:
            final_result["signature"] = signature
            final_result["signature_kid"] = signature_kid
        return final_result, reset_content


def build_stream_result_postprocessor(
    request: CompatibilityRequest,
    context: StandardExecutionContext | None,
) -> StreamResultPostProcessor | None:
    """Create terminal stream policy from prepared orchestration state.

    HTTP handlers pass only request-scoped host ports through
    :class:`StandardExecutionContext`; the compatibility executor owns the
    source-scope, memory, reasoning, and retrieval-strategy binding.
    """
    if context is None:
        return None

    return StreamResultPostProcessor(
        context=StreamPostExecutionContext(
            allowed_sources=list(request.source_scope.allowed_sources or ()),
            question=request.question,
            memory_context="\n".join(message.content for message in request.conversation),
            use_reasoning=request.use_reasoning,
            retrieval_strategy=request.retrieval_strategy,
            trace_id=context.trace_id,
        ),
        sign_result=context.result_signer or (lambda _result: (None, None)),
        audit_source_scope=context.source_scope_audit,
    )


__all__ = [
    "StandardExecutionContext",
    "StandardPostExecutionServices",
    "build_standard_post_execution_services",
    "StreamPostExecutionContext",
    "StreamResultPostProcessor",
    "build_stream_result_postprocessor",
    "execute_standard_compatibility",
    "enforce_result_source_scope",
    "resynthesize_after_source_scope",
]
