"""Tests degradation behavior for concurrent typed retrieval."""

import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.domain.events import ExecutionEvent
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_rag_service_keeps_available_evidence_and_reports_failed_retriever() -> None:
    """Replacing isolated failure handling with gather's default must fail this test."""
    events: list[ExecutionEvent] = []

    async def vector(*_args: object) -> EvidenceBundle:
        raise TimeoutError("vector timeout")

    async def bm25(*_args: object) -> EvidenceBundle:
        return EvidenceBundle()

    async def graph(*_args: object) -> EvidenceBundle:
        return EvidenceBundle(
            items=(EvidenceItem(content="Graph fact", source="graph", document_id="entity-1", score=0.8),)
        )

    async def report(event: ExecutionEvent) -> None:
        events.append(event)

    route = RouteDecision(
        intent="hybrid",
        confidence=0.9,
        requires_plan=True,
        allowed_capabilities=frozenset({"rag"}),
        reason="hybrid",
    )
    evidence = await RAGAgentService(vector=vector, bm25=bm25, graph=graph, report_degradation=report).retrieve(
        OrchestrationRequest(question="Compare"), route, None
    )

    assert evidence.items[0].document_id == "entity-1"
    assert [(event.stage, event.status, event.message) for event in events] == [
        ("rag", "skipped", "vector: TimeoutError: vector retriever exceeded timeout (30.0s)"),
        ("rag", "completed", "DEGRADED: Partial retrieval success: 2/3 attempts, 1 evidence items. Failed: vector"),
    ]
