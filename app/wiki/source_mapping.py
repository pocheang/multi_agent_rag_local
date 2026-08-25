"""Map governed original Evidence into durable Wiki source references."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.privacy.dlp import mask_evidence
from app.wiki.models import WikiSourceReference


def governed_evidence(
    evidence: Iterable[EvidenceItem],
    scope: AccessScope,
) -> tuple[EvidenceItem, ...]:
    """Keep only authorized original evidence with usable, versioned content."""

    output: list[EvidenceItem] = []
    for item in evidence:
        if item.layer != "evidence" or item.version is None:
            continue
        masked = mask_evidence(item, scope)
        if masked is None or masked.content == "[REDACTED_FIELD]" or not masked.content.strip():
            continue
        output.append(masked)
    return tuple(output)


def references_from_evidence(evidence: Iterable[EvidenceItem]) -> tuple[WikiSourceReference, ...]:
    references: list[WikiSourceReference] = []
    for item in evidence:
        if item.layer != "evidence" or item.version is None:
            continue
        references.append(
            WikiSourceReference(
                source=item.source,
                document_id=item.document_id,
                document_version=item.version,
                page=item.page,
                chunk_id=item.chunk_id,
                image_id=item.image_id,
                acl_tags=item.acl_tags,
            )
        )
    return tuple(references)


__all__ = ["governed_evidence", "references_from_evidence"]
