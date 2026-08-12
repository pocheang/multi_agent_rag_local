"""Regression tests for real legacy retrieval adapter edge cases."""

from unittest.mock import patch

import pytest

from app.agents.rag.service import RetrieverSoftFailure, _bundle_from_legacy_payload, _graph_retrieve
from app.domain.contracts import RouteDecision
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_graph_adapter_preserves_context_when_legacy_graph_has_no_citations() -> None:
    """Dropping a citation-less graph result would discard successful graph retrieval."""
    with patch(
        "app.agents.graph_rag_agent.run_graph_rag",
        return_value={"context": "Transformer USES Attention", "graph_signal_score": 0.8},
    ):
        evidence = await _graph_retrieve(
            OrchestrationRequest(question="Transformer"),
            RouteDecision(
                intent="hybrid",
                confidence=0.9,
                requires_plan=True,
                allowed_capabilities=frozenset({"rag"}),
                reason="comparison",
            ),
            None,
        )

    assert evidence.items[0].document_id == "graph:Transformer"
    assert evidence.items[0].content == "Transformer USES Attention"


def test_legacy_error_payload_is_a_retriever_failure_not_empty_evidence() -> None:
    """Ignoring an explicit legacy error would hide a degradation event from callers."""
    with pytest.raises(RetrieverSoftFailure, match="upstream unavailable"):
        _bundle_from_legacy_payload({"error": "upstream unavailable"}, "web")
