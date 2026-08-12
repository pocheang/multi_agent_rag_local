"""Authorization-boundary tests for typed retrieval."""

import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceBundle, RouteDecision
from app.orchestration.request import OrchestrationRequest, RequestScope


@pytest.mark.asyncio
async def test_rag_service_never_searches_when_source_scope_is_explicitly_empty() -> None:
    """Converting an empty authorization scope to None would leak all indexed documents."""
    calls: list[str] = []

    def retriever(name: str):
        async def run(*_args: object) -> EvidenceBundle:
            calls.append(name)
            return EvidenceBundle()

        return run

    evidence = await RAGAgentService(vector=retriever("vector"), bm25=retriever("bm25")).retrieve(
        OrchestrationRequest(question="restricted", source_scope=RequestScope(allowed_sources=frozenset())),
        RouteDecision(
            intent="knowledge_retrieval",
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="direct",
        ),
        None,
    )

    assert evidence == EvidenceBundle()
    assert calls == []
