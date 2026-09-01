"""Evidence with no version must still be citable.

`EvidenceRef.version` used to be required while `EvidenceItem.version` was
optional. Web results and graph context have no version, so every marker aimed
at them was dropped: a web-routed answer came back with zero citations, the
verifier saw "no attributable citation", and the whole run finished degraded
with an empty citation list.
"""

from __future__ import annotations

import pytest

from app.agents.synthesizer.service import SynthesizerAgentService
from app.domain.contracts import EvidenceItem
from app.domain.workflow import ContextBundle
from app.orchestration.request import OrchestrationRequest


def _context(*items: EvidenceItem) -> ContextBundle:
    rendered = "\n\n".join(
        f"[E{index}] document={item.document_id}; source={item.source}\n{item.content}"
        for index, item in enumerate(items, start=1)
    )
    return ContextBundle(evidence=items, rendered_context=rendered)


def _generate(answer: str):
    def generate(*_args: object, **_kwargs: object) -> dict:
        return {"answer": answer}

    return generate


@pytest.mark.asyncio
async def test_a_web_result_without_a_version_still_becomes_a_citation():
    web = EvidenceItem(
        content="RAG combines retrieval with generation.",
        source="https://example.com/rag",
        document_id="https://example.com/rag",
        version=None,
        layer="web",
        retriever="web",
    )
    service = SynthesizerAgentService(generate=_generate("RAG is retrieval-augmented generation [E1]."))

    candidate = await service.synthesize_candidate(
        OrchestrationRequest(question="What is RAG?"),
        _context(web),
        (),
    )

    assert len(candidate.citations) == 1
    assert candidate.citations[0].document_id == "https://example.com/rag"
    assert candidate.citations[0].version is None
    assert "missing_citations" not in candidate.unresolved_items


@pytest.mark.asyncio
async def test_an_answer_that_cites_nothing_is_still_reported_as_uncited():
    versioned = EvidenceItem(
        content="Paris is the capital of France.",
        source="geography.pdf",
        document_id="geography.pdf",
        version=1,
        page=3,
        retriever="vector",
    )
    service = SynthesizerAgentService(generate=_generate("Paris is the capital of France."))

    candidate = await service.synthesize_candidate(
        OrchestrationRequest(question="Capital of France?"),
        _context(versioned),
        (),
    )

    assert candidate.citations == ()
    assert "missing_citations" in candidate.unresolved_items
