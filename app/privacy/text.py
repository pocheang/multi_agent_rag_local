"""Shared deterministic PII and secret inspection for workflow boundaries."""

from __future__ import annotations

from collections.abc import Iterable

from app.privacy.models import PrivacyFinding, TextPrivacyResult
from app.services.security.outbound_redaction import redact_sensitive_text

PII_KINDS = frozenset({"EMAIL", "PHONE", "IP", "UUID", "PATH"})
SECRET_KINDS = frozenset({"SECRET"})
INPUT_KINDS = PII_KINDS | SECRET_KINDS | frozenset({"URL", "CUSTOM"})
OUTPUT_KINDS = PII_KINDS | SECRET_KINDS | frozenset({"CUSTOM"})


def inspect_text(text: str, *, kinds: Iterable[str] = INPUT_KINDS) -> TextPrivacyResult:
    """Return stable tokenization plus counts, never the matched values."""

    selected = frozenset(str(kind).strip().upper() for kind in kinds if str(kind).strip())
    sanitized, counts = redact_sensitive_text(str(text or ""), allowed_kinds=selected)
    findings = tuple(
        PrivacyFinding(
            kind=kind,
            category="secret" if kind in SECRET_KINDS else "pii",
            count=count,
        )
        for kind, count in sorted(counts.items())
        if count > 0
    )
    return TextPrivacyResult(
        text=sanitized,
        findings=findings,
        redaction_count=sum(item.count for item in findings),
    )


__all__ = ["INPUT_KINDS", "OUTPUT_KINDS", "PII_KINDS", "SECRET_KINDS", "inspect_text"]
