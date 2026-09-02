"""Context masking and output DLP over authorized evidence only."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.privacy.models import DLPResult, PrivacyFinding
from app.privacy.text import OUTPUT_KINDS, inspect_text
from app.services.answer_safety import sanitize_answer

_CONTENT_FIELDS = frozenset(
    {"content", "source", "document_id", "version", "page", "chunk_id", "image_id", "artifact_uri"}
)


def memory_source_prefix(scope: AccessScope) -> str:
    """The `memory://` namespace one scope owns; see app/knowledge/adapters.py."""

    return f"memory://{scope.tenant_id}/{scope.user_id}/"


def evidence_is_authorized(item: EvidenceItem, scope: AccessScope) -> bool:
    """Enforce document/source restrictions before evidence reaches a model."""

    # Web and tool results are not user documents and carry no owner to check.
    if item.layer in {"web", "tool"}:
        return True
    # Memory is owner-scoped by its store layout rather than by allowed_sources
    # (a `memory://` URI is never a document path), so check the namespace it
    # declares instead of exempting the layer outright.
    if item.layer == "memory":
        return item.source.startswith(memory_source_prefix(scope))
    if not scope.document_ids and not scope.allowed_sources:
        return False
    if scope.document_ids and item.document_id not in scope.document_ids:
        return False
    if scope.allowed_sources and item.source not in scope.allowed_sources:
        return False
    if item.acl_tags and not item.acl_tags.intersection(scope.acl_tags):
        return False
    return True


def mask_evidence(item: EvidenceItem, scope: AccessScope) -> EvidenceItem | None:
    """Drop unauthorized evidence and redact sensitive authorized fields."""

    if not evidence_is_authorized(item, scope):
        return None
    allowed_fields = scope.allowed_fields.intersection(_CONTENT_FIELDS)
    content = "[REDACTED_FIELD]"
    if "content" in allowed_fields:
        content = inspect_text(item.content, kinds=OUTPUT_KINDS).text
    return item.model_copy(
        update={
            "content": content,
            "artifact_uri": item.artifact_uri if "artifact_uri" in allowed_fields else None,
        }
    )


def filter_output(answer: str, citations: Sequence[EvidenceItem], scope: AccessScope) -> DLPResult:
    """Apply secret sanitization, PII redaction, and citation authorization."""

    secret_safe, secret_meta = sanitize_answer(str(answer or ""))
    inspected = inspect_text(secret_safe, kinds=OUTPUT_KINDS)
    kept: list[EvidenceItem] = []
    dropped: list[str] = []
    for citation in citations:
        masked = mask_evidence(citation, scope)
        if masked is None:
            dropped.append(citation.item_id)
        else:
            kept.append(masked)
    findings = list(inspected.findings)
    secret_redactions = int(secret_meta.get("redactions", 0) or 0)
    if secret_redactions:
        findings.append(PrivacyFinding(kind="SECRET", category="secret", count=secret_redactions))
    return DLPResult(
        answer=inspected.text,
        citations=tuple(kept),
        findings=tuple(findings),
        redaction_count=inspected.redaction_count + secret_redactions,
        dropped_citation_ids=tuple(dropped),
    )


__all__ = ["evidence_is_authorized", "filter_output", "mask_evidence"]
