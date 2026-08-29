"""Regression test: SynthesizerAgentService.synthesize() must label citations
the same way app/orchestration/langgraph/nodes.py does (by `source`, not
`document_id`) so the fallback synthesis path never disagrees with the live
LangGraph path on what a citation label means."""

from __future__ import annotations

import pytest

from app.agents.synthesizer.service import SynthesizerAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.orchestration.request import OrchestrationRequest


def _fake_generate(*_args: object, **_kwargs: object) -> dict:
    return {"answer": "Paris is the capital of France [E1]."}


@pytest.mark.asyncio
async def test_citation_label_uses_source_not_document_id():
    item = EvidenceItem(
        content="Paris is the capital of France.",
        source="https://example.com/geography-article",
        document_id="internal-doc-42",
        version=1,
        page=3,
        retriever="vector",
    )
    evidence = EvidenceBundle(items=(item,))
    route = RouteDecision(confidence=0.9, requires_plan=False, allowed_capabilities=frozenset(), reason="test route")
    request = OrchestrationRequest(question="What is the capital of France?")
    service = SynthesizerAgentService(generate=_fake_generate)

    result = await service.synthesize(request, route, None, evidence, ())

    assert result.citations == ("https://example.com/geography-article:3",)
    assert "internal-doc-42:3" not in result.citations
