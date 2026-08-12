"""Tests default propagation of typed RAG degradation events through the engine publisher."""

from types import SimpleNamespace

import pytest

from app.agents.rag.service import RAGAgentService
from app.agents.router.service import RouterAgentService
from app.agents.synthesizer.service import SynthesizerAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem
from app.orchestration.engine import OrchestrationEngine
from app.orchestration.event_publisher import InMemoryEventPublisher
from app.orchestration.request import OrchestrationRequest
from app.pipeline.adapters import CoreCapabilities


@pytest.mark.asyncio
async def test_core_capabilities_publish_rag_retriever_degradation_events() -> None:
    """Dropping the service reporter during assembly hides degradation from orchestration clients."""
    async def vector(*_args: object) -> EvidenceBundle:
        raise TimeoutError("vector timeout")

    async def bm25(*_args: object) -> EvidenceBundle:
        return EvidenceBundle(
            items=(EvidenceItem(content="fallback", source="guide.pdf", document_id="guide", score=0.8),)
        )

    capabilities = CoreCapabilities(
        typed_router=RouterAgentService(
            decider=lambda *_args, **_kwargs: SimpleNamespace(route="vector", confidence=0.9, reason="direct")
        ),
        typed_rag=RAGAgentService(vector=vector, bm25=bm25),
        typed_synthesizer=SynthesizerAgentService(generate=lambda *_args, **_kwargs: "fallback [guide]"),
    )
    publisher = InMemoryEventPublisher()

    await OrchestrationEngine(
        services=capabilities.orchestration_services(), publisher=publisher
    ).execute(OrchestrationRequest(question="Question"))

    assert [(event.stage, event.status, event.message) for event in publisher.events] == [
        ("route", "completed", ""),
        ("rag", "skipped", "vector: TimeoutError"),
        ("rag", "completed", ""),
        ("synthesize", "completed", ""),
        ("complete", "completed", ""),
    ]
