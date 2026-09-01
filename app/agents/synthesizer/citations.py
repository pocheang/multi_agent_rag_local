"""Citation-label extraction, answer normalization, and reference numbering.

Two marker formats live here and they are not interchangeable.  ``[E1]`` is the
*internal* evidence marker: it is what ``ContextBuilder`` renders in front of
each excerpt, what the prompts teach, and what ``normalize_answer_citations``
allow-lists, so it always names an exact position in the evidence list.
``[1]`` is the *reader-facing* marker produced at the very end of the run by
``number_evidence_markers``, numbered by first appearance the way a paper's
reference list is.  Nothing between synthesis and the output filter should have
to know about the second form.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from pathlib import Path

from app.domain.contracts import EvidenceItem

_CITATION_LABEL_PATTERN = r"[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?"
_EVIDENCE_RECORD_RE = re.compile(rf"(?m)^\s*\[({_CITATION_LABEL_PATTERN})\][ \t]+\S")
_CITATION_LABEL_RE = re.compile(rf"^{_CITATION_LABEL_PATTERN}$")
_BRACKETED_MARKER_RE = re.compile(r"\[([^\]\r\n]+)\](?!\()")

EVIDENCE_MARKER_RE = re.compile(r"\[E(\d+)\]")
"""The one place the internal evidence-marker shape is defined."""

_REFERENCE_HEADINGS = {"zh": "参考来源", "en": "References"}


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

    return _tidy_spacing(_BRACKETED_MARKER_RE.sub(replace_marker, str(text or "")))


def number_evidence_markers(
    text: str,
    evidence: Sequence[EvidenceItem],
    *,
    keep_item_ids: Collection[str] | None = None,
) -> tuple[str, tuple[EvidenceItem, ...]]:
    """Rewrite internal ``[E{k}]`` markers as reader-facing ``[1]``, ``[2]``, ...

    Numbers are assigned in order of *first appearance in the answer*, not in
    retrieval order, so the returned reference list reads top-down the way a
    paper's does and never has gaps for evidence the model did not cite.

    Two excerpts a reader would see as the same source -- same ``source`` and
    same ``page`` -- share one number, because rendering ``[1]`` and ``[2]`` as
    two identical reference lines reads as a bug.  The first of them becomes the
    reference entry.

    ``keep_item_ids`` is the set that survived output filtering.  A marker
    pointing at anything else, or past the end of the evidence list, is removed
    rather than left dangling: a ``[n]`` with no entry to resolve to is worse
    than no citation at all.

    Returns the rewritten text and the reference items in numbered order, so
    ``references[n - 1]`` is what ``[n]`` in the text points at.
    """

    references: list[EvidenceItem] = []
    numbers: dict[tuple[str, int | None], int] = {}
    allowed = None if keep_item_ids is None else frozenset(keep_item_ids)

    def renumber(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index < 1 or index > len(evidence):
            return ""
        item = evidence[index - 1]
        if allowed is not None and item.item_id not in allowed:
            return ""
        key = _reference_key(item)
        number = numbers.get(key)
        if number is None:
            number = len(references) + 1
            numbers[key] = number
            references.append(item)
        return f"[{number}]"

    return _tidy_spacing(EVIDENCE_MARKER_RE.sub(renumber, str(text or ""))), tuple(references)


def reference_label(item: EvidenceItem, language: str = "zh") -> str:
    """Name one source the way a reader identifies it, not the way the store does.

    Local evidence is shown by filename: ``item.source`` is a storage path, and
    the directory part identifies the tenant layout rather than the document.
    Web evidence keeps its full URL, which is the only thing that identifies it.
    """

    source = str(item.source or "").strip()
    if source.startswith(("http://", "https://")):
        name = source
    else:
        name = Path(source).name or source
    if item.page is None:
        return name
    return f"{name} · 第 {item.page} 页" if language == "zh" else f"{name} · p. {item.page}"


def render_reference_list(references: Sequence[EvidenceItem], language: str = "zh") -> str:
    """Render the numbered source list appended after a finished answer.

    Emitted as a markdown list because the client renders answers through
    ``react-markdown`` without ``remark-breaks``: plain newlines would collapse
    every entry onto a single line.
    """

    if not references:
        return ""
    heading = _REFERENCE_HEADINGS.get(language, _REFERENCE_HEADINGS["zh"])
    lines = [f"**{heading}**", ""]
    lines.extend(f"- [{number}] {reference_label(item, language)}" for number, item in enumerate(references, start=1))
    return "\n".join(lines)


def _reference_key(item: EvidenceItem) -> tuple[str, int | None]:
    return (item.source, item.page)


def _tidy_spacing(text: str) -> str:
    """Close the gap a removed marker leaves without disturbing line structure."""
    tidied = re.sub(r"[ \t]+([,.;:!?])", r"\1", str(text or ""))
    tidied = re.sub(r"(?<!\n)[ \t]{2,}", " ", tidied)
    return tidied.strip()


__all__ = [
    "EVIDENCE_MARKER_RE",
    "citation_labels_from_contexts",
    "normalize_answer_citations",
    "number_evidence_markers",
    "reference_label",
    "render_reference_list",
]
