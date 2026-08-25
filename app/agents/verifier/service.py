"""Bounded answer verification over candidate text and authorized context."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings
from app.domain.knowledge import EvidenceRef
from app.domain.workflow import CandidateAnswer, ContextBundle, VerificationDecision
from app.orchestration.request import OrchestrationRequest
from app.services.retrieval.evidence_conflict import detect_evidence_conflict

Validator = Callable[
    [str, str, Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]],
    Awaitable[Any],
]


class VerifierAgentService:
    """Check support, citations, omissions, and conflicts with at most one retry."""

    def __init__(
        self,
        validator: Validator | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._validator = validator or _validate
        active = settings or get_settings()
        self._max_retries = max(0, min(1, int(active.verifier_max_retries)))

    async def verify(
        self,
        request: OrchestrationRequest,
        context: ContextBundle,
        candidate: CandidateAnswer,
        retry_count: int,
    ) -> VerificationDecision:
        citation_errors = _citation_errors(candidate.citations, context)
        conflicts = _conflicts(context)
        missing_aspects = list(candidate.unresolved_items)
        if context.evidence and not candidate.citations:
            missing_aspects.append("answer has no attributable citation")
        if not context.evidence:
            missing_aspects.append("no authorized evidence retrieved")

        documents = [
            {
                "id": item.document_id,
                "doc_id": item.document_id,
                "content": item.content,
                "source": item.source,
                "page": item.page,
                "chunk_id": item.chunk_id,
                "image_id": item.image_id,
            }
            for item in context.evidence
        ]
        citations = [
            {
                "doc_id": ref.document_id,
                "content": _citation_content(ref, context),
                "page": ref.page,
                "chunk_id": ref.chunk_id,
                "image_id": ref.image_id,
            }
            for ref in candidate.citations
        ]
        try:
            result = await self._validator(request.question, candidate.text, documents, citations)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return self._validation_unavailable(request, retry_count, type(exc).__name__, conflicts)

        issues = tuple(getattr(result, "issues", ()) or ())
        unsupported = [
            str(getattr(issue, "content", "unsupported claim") or "unsupported claim")
            for issue in issues
            if str(getattr(issue, "type", "")).lower() in {"unsupported_claim", "hallucination"}
        ]
        safety_issues = [
            str(getattr(issue, "content", "safety issue") or "safety issue")
            for issue in issues
            if str(getattr(issue, "type", "")).lower() == "safety"
        ]
        missing_aspects.extend(
            "citation coverage is incomplete"
            for issue in issues
            if str(getattr(issue, "type", "")).lower() == "missing_citation"
        )
        details = getattr(result, "validation_details", None)
        factuality = float(getattr(details, "factual_consistency", 1.0) or 0.0)
        citation_completeness = float(getattr(details, "citation_completeness", 1.0) or 0.0)
        if factuality < 0.7 and not unsupported:
            unsupported.append("answer factual support is below threshold")
        if candidate.citations and citation_completeness < 1.0:
            missing_aspects.append("one or more citations do not resolve to supplied evidence")

        unsupported_tuple = tuple(dict.fromkeys(unsupported))
        citation_tuple = tuple(dict.fromkeys(citation_errors))
        missing_tuple = tuple(dict.fromkeys(missing_aspects))
        if safety_issues:
            return VerificationDecision(
                status="rejected",
                unsupported_claims=tuple(dict.fromkeys(safety_issues)),
                citation_errors=citation_tuple,
                conflicts=conflicts,
                missing_aspects=missing_tuple,
            )

        action = str(getattr(result, "action", "regenerate") or "regenerate")
        needs_retrieval = bool(
            action == "regenerate" or unsupported_tuple or citation_tuple or missing_tuple
        )
        if needs_retrieval and retry_count < self._max_retries:
            return VerificationDecision(
                status="retry_retrieval",
                unsupported_claims=unsupported_tuple,
                citation_errors=citation_tuple,
                conflicts=conflicts,
                missing_aspects=missing_tuple,
                retry_query=_retry_query(request.question, unsupported_tuple, citation_tuple, missing_tuple),
            )
        if needs_retrieval:
            status = "rejected" if action == "regenerate" or unsupported_tuple or citation_tuple else "degraded"
            return VerificationDecision(
                status=status,
                unsupported_claims=unsupported_tuple,
                citation_errors=citation_tuple,
                conflicts=conflicts,
                missing_aspects=missing_tuple,
            )
        if action == "flag":
            return VerificationDecision(status="degraded", conflicts=conflicts)
        return VerificationDecision(status="approved", conflicts=conflicts)

    def _validation_unavailable(
        self,
        request: OrchestrationRequest,
        retry_count: int,
        error_type: str,
        conflicts: tuple[str, ...],
    ) -> VerificationDecision:
        missing = (f"verification unavailable:{error_type}",)
        if retry_count < self._max_retries:
            return VerificationDecision(
                status="retry_retrieval",
                conflicts=conflicts,
                missing_aspects=missing,
                retry_query=_retry_query(request.question, (), (), missing),
            )
        return VerificationDecision(status="degraded", conflicts=conflicts, missing_aspects=missing)


async def _validate(
    query: str,
    answer: str,
    documents: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> Any:
    from app.agents.validation.public import validate_answer

    return await validate_answer(query, answer, documents, citations)


def _citation_errors(refs: tuple[EvidenceRef, ...], context: ContextBundle) -> list[str]:
    valid = {
        (item.document_id, item.version, item.page, item.chunk_id, item.image_id)
        for item in context.evidence
    }
    return [
        f"citation target not found:{ref.document_id}:v{ref.version}"
        for ref in refs
        if (ref.document_id, ref.version, ref.page, ref.chunk_id, ref.image_id) not in valid
    ]


def _citation_content(ref: EvidenceRef, context: ContextBundle) -> str:
    key = (ref.document_id, ref.version, ref.page, ref.chunk_id, ref.image_id)
    for item in context.evidence:
        if (item.document_id, item.version, item.page, item.chunk_id, item.image_id) == key:
            return item.content
    return ""


def _conflicts(context: ContextBundle) -> tuple[str, ...]:
    notes = [str(value) for value in context.diagnostics.get("context_conflicts", ()) or ()]
    detected = detect_evidence_conflict(
        [{"content": item.content, "layer": item.layer, "source": item.source} for item in context.evidence]
    )
    if detected.get("conflict"):
        notes.extend(str(value) for value in detected.get("examples", ()) or ())
    return tuple(dict.fromkeys(notes))


def _retry_query(
    question: str,
    unsupported: tuple[str, ...],
    citation_errors: tuple[str, ...],
    missing: tuple[str, ...],
) -> str:
    categories = []
    if unsupported:
        categories.append("unsupported claims")
    if citation_errors:
        categories.append("citation targets")
    if missing:
        categories.append("missing evidence")
    focus = ", ".join(categories) or "verification gaps"
    return f"{question}\nRetrieve additional primary evidence for: {focus}."[:1_000]


__all__ = ["Validator", "VerifierAgentService"]
