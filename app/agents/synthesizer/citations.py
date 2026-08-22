"""Citation-label extraction and answer normalization for synthesis."""

from __future__ import annotations

import re
from collections.abc import Collection

_CITATION_LABEL_PATTERN = r"[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?"
_EVIDENCE_RECORD_RE = re.compile(rf"(?m)^\s*\[({_CITATION_LABEL_PATTERN})\][ \t]+\S")
_CITATION_LABEL_RE = re.compile(rf"^{_CITATION_LABEL_PATTERN}$")
_BRACKETED_MARKER_RE = re.compile(r"\[([^\]\r\n]+)\](?!\()")


def citation_labels_from_contexts(*contexts: str) -> frozenset[str]:
    """Return labels from leading ``[label] content`` evidence records."""
    return frozenset(
        label.strip() for context in contexts for label in _EVIDENCE_RECORD_RE.findall(context or "") if label.strip()
    )


def normalize_answer_citations(text: str, allowed_labels: Collection[str]) -> str:
    """Preserve allowed citations and remove non-allowlisted citation markers."""
    allowed = frozenset(str(label).strip() for label in allowed_labels if str(label).strip())

    def replace_marker(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        if label in allowed or not _CITATION_LABEL_RE.fullmatch(label):
            return match.group(0)
        return ""

    normalized = _BRACKETED_MARKER_RE.sub(replace_marker, str(text or ""))
    normalized = re.sub(r"[ \t]+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"(?<!\n)[ \t]{2,}", " ", normalized)
    return normalized.strip()
