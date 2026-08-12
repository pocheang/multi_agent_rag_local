"""Pure evidence fusion rules shared by typed retrieval adapters."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.contracts import EvidenceBundle, EvidenceItem


def fuse_evidence(bundles: Iterable[EvidenceBundle]) -> EvidenceBundle:
    """Deduplicate by document/page and retain the highest-scored evidence item."""
    winners: dict[tuple[str, int | None], EvidenceItem] = {}
    for bundle in bundles:
        for item in bundle.items:
            key = (item.document_id, item.page)
            current = winners.get(key)
            if current is None or _score(item) > _score(current):
                winners[key] = item

    items = tuple(sorted(winners.values(), key=_score, reverse=True))
    return EvidenceBundle(items=items)


def _score(item: EvidenceItem) -> float:
    """Treat a missing score as lower than every scored retrieval hit."""
    return item.score if item.score is not None else -1.0
