"""Behavioral tests for typed evidence fusion."""

from app.agents.rag.fusion import fuse_evidence
from app.domain.contracts import EvidenceBundle, EvidenceItem


def test_fuse_evidence_keeps_highest_scored_duplicate_with_provenance() -> None:
    """Replacing duplicate selection with first-hit wins must fail this test."""
    low_score = EvidenceItem(
        item_id="vector-copy",
        content="Older chunk",
        source="handbook.pdf",
        document_id="handbook",
        page=12,
        retriever="vector",
        score=0.42,
    )
    high_score = EvidenceItem(
        item_id="graph-copy",
        content="Authoritative chunk",
        source="handbook.pdf",
        document_id="handbook",
        page=12,
        retriever="graph",
        score=0.93,
    )
    independent = EvidenceItem(
        item_id="web-source",
        content="Independent evidence",
        source="https://example.org/rag",
        document_id="web-rag",
        retriever="web",
        score=0.71,
    )

    fused = fuse_evidence(
        (
            EvidenceBundle(items=(low_score, independent)),
            EvidenceBundle(items=(high_score,)),
        )
    )

    assert fused.items == (high_score, independent)
    assert fused.items[0].source == "handbook.pdf"
    assert fused.items[0].document_id == "handbook"
    assert fused.items[0].page == 12
