"""Behavioral tests for immutable orchestration domain contracts."""

import pytest
from pydantic import ValidationError

from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision


def test_evidence_item_rejects_blank_source() -> None:
    """A missing provenance source must never enter an evidence bundle."""
    with pytest.raises(ValidationError, match="source"):
        EvidenceItem(content="The answer", source="   ", document_id="doc-1")


def test_route_decision_is_immutable() -> None:
    """Route choices must not be changed after crossing an orchestration boundary."""
    decision = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.91,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="A direct factual lookup is sufficient.",
    )

    with pytest.raises(ValidationError):
        decision.intent = "tool_call"  # type: ignore[misc]


def test_evidence_bundle_keeps_immutable_evidence_items() -> None:
    """Bundle consumers receive tuples instead of mutable cross-layer lists."""
    item = EvidenceItem(content="A fact", source="handbook.pdf", document_id="handbook", page=3)

    bundle = EvidenceBundle(items=(item,))

    assert bundle.items == (item,)
