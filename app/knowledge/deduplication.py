"""Stable provenance-aware evidence deduplication."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from app.domain.contracts import EvidenceItem

_SPACE_RE = re.compile(r"\s+")


def evidence_dedup_key(item: EvidenceItem) -> tuple[str, tuple[object, ...]]:
    """Prefer immutable artifact identifiers and fall back to canonical content.

    Always ``(kind, payload)``. The two kinds are computed from different fields
    and would otherwise be free to meet in the same dictionary, so the kind is
    not decoration -- it is the only thing keeping a content key and a
    provenance key apart. Keeping it out of the payload says that, where a
    variable-length tuple with a discriminant at position zero only implied it.
    """

    if item.chunk_id or item.image_id:
        return ("provenance", (item.document_id, item.version, item.chunk_id, item.image_id))

    canonical_content = _SPACE_RE.sub(" ", item.content).strip().lower()
    digest = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()
    return ("content", (item.source.strip().lower(), item.page, digest))


def deduplicate_evidence(items: Iterable[EvidenceItem]) -> tuple[EvidenceItem, ...]:
    """Keep the highest score for each artifact and merge retriever labels."""

    winners: dict[tuple[str, tuple[object, ...]], EvidenceItem] = {}
    labels: dict[tuple[str, tuple[object, ...]], set[str]] = {}
    for item in items:
        key = evidence_dedup_key(item)
        labels.setdefault(key, set()).update(_retriever_labels(item.retriever))
        current = winners.get(key)
        if current is None or _score(item) > _score(current):
            winners[key] = item

    merged = [item.model_copy(update={"retriever": "+".join(sorted(labels[key]))}) for key, item in winners.items()]
    return tuple(sorted(merged, key=_score, reverse=True))


def _retriever_labels(value: str) -> set[str]:
    return {label.strip() for label in value.split("+") if label.strip()} or {"unknown"}


def _score(item: EvidenceItem) -> float:
    return item.score if item.score is not None else -1.0


__all__ = ["deduplicate_evidence", "evidence_dedup_key"]
