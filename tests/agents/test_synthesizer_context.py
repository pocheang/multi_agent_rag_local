"""Tests that typed evidence reaches legacy synthesis with citation labels."""

import pytest

from app.agents.synthesizer.citations import (
    citation_labels_from_contexts,
    normalize_answer_citations,
)
from app.agents.synthesizer.generation import SYNTHESIS_FALLBACK_MESSAGE
from app.agents.synthesizer.service import SynthesizerAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_synthesizer_supplies_citation_labeled_evidence_context() -> None:
    """Removing the evidence label from model context would break citation-first generation."""
    received: dict[str, object] = {}

    def generate(*_args: object, **kwargs: object) -> str:
        received.update(kwargs)
        return "RAG uses retrieved evidence [guide:7]."

    answer = await SynthesizerAgentService(generate=generate).synthesize(
        OrchestrationRequest(question="What is RAG?"),
        RouteDecision(
            intent="knowledge_retrieval",
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="direct",
        ),
        None,
        EvidenceBundle(
            items=(EvidenceItem(content="RAG definition", source="guide.pdf", document_id="guide", page=7),)
        ),
        (),
    )

    assert received["vector_context"] == "[guide:7] RAG definition"
    assert answer.citations == ("guide:7",)

@pytest.mark.asyncio
async def test_synthesizer_rejects_evidence_backed_answer_without_a_visible_citation() -> None:
    """Accepting a factual answer with no supplied evidence label breaks the citation contract."""
    service = SynthesizerAgentService(generate=lambda *_args, **_kwargs: "RAG uses retrieved evidence.")

    with pytest.raises(ValueError, match="citation"):
        await service.synthesize(
            OrchestrationRequest(question="What is RAG?"),
            RouteDecision(
                intent="knowledge_retrieval",
                confidence=0.9,
                requires_plan=False,
                allowed_capabilities=frozenset({"rag"}),
                reason="direct",
            ),
            None,
            EvidenceBundle(
                items=(EvidenceItem(content="RAG definition", source="guide.pdf", document_id="guide", page=7),)
            ),
            (),
        )


@pytest.mark.asyncio
async def test_synthesizer_strips_invented_markers_without_evidence() -> None:
    """Typed synthesis must return no citations when no evidence was provided."""
    answer = await SynthesizerAgentService(
        generate=lambda *_args, **_kwargs: "Hello! [fake:99]"
    ).synthesize(
        OrchestrationRequest(question="hi"),
        RouteDecision(
            intent="general_qa",
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset(),
            reason="direct",
        ),
        None,
        EvidenceBundle(items=()),
        (),
    )

    assert answer.text == "Hello!"
    assert answer.citations == ()


def test_citation_labels_ignore_bracketed_prose_and_preserve_markdown() -> None:
    """Only grammar-shaped leading labels may turn on citation mode."""
    labels = citation_labels_from_contexts(
        "[draft note] This is ordinary prose",
        "[guide:7] RAG definition",
    )

    answer = normalize_answer_citations(
        "See [draft note] and [OpenAI](https://openai.com) [guide:7] [fake:99].",
        labels,
    )

    assert labels == frozenset({"guide:7"})
    assert answer == "See [draft note] and [OpenAI](https://openai.com) [guide:7]."


@pytest.mark.asyncio
async def test_synthesizer_uses_fallback_when_empty_evidence_normalizes_to_blank() -> None:
    """An invented-only empty-evidence result must not become a blank final answer."""
    answer = await SynthesizerAgentService(
        generate=lambda *_args, **_kwargs: "[fake:99]"
    ).synthesize(
        OrchestrationRequest(question="hi"),
        RouteDecision(
            intent="general_qa",
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset(),
            reason="direct",
        ),
        None,
        EvidenceBundle(items=()),
        (),
    )

    assert answer.text == SYNTHESIS_FALLBACK_MESSAGE
    assert answer.citations == ()


@pytest.mark.asyncio
async def test_synthesizer_strips_invented_marker_but_keeps_valid_typed_evidence() -> None:
    """Typed evidence answers retain only supplied visible labels."""
    answer = await SynthesizerAgentService(
        generate=lambda *_args, **_kwargs: "RAG evidence [guide:7] [fake:99]."
    ).synthesize(
        OrchestrationRequest(question="What is RAG?"),
        RouteDecision(
            intent="knowledge_retrieval",
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="direct",
        ),
        None,
        EvidenceBundle(
            items=(
                EvidenceItem(
                    content="RAG definition",
                    source="guide.pdf",
                    document_id="guide",
                    page=7,
                ),
            )
        ),
        (),
    )

    assert answer.text == "RAG evidence [guide:7]."
    assert answer.citations == ("guide:7",)
