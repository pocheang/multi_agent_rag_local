"""Tests for degradation policy functionality."""

import pytest

from app.agents.rag.service import (
    RAGAgentService,
    RequireAtLeastOnePolicy,
    RequireMinimumCountPolicy,
    RequireSpecificRetrieverPolicy,
    RetrievalFailureError,
)
from app.domain.contracts import EvidenceBundle, RouteDecision
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_require_at_least_one_policy_default():
    """Default policy allows any single success."""

    async def failing_vector(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("Vector failed")

    async def succeeding_bm25(*_args, **_kwargs) -> EvidenceBundle:
        return EvidenceBundle()

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    # Default policy (RequireAtLeastOnePolicy)
    service = RAGAgentService(vector=failing_vector, bm25=succeeding_bm25)

    # Should succeed because bm25 succeeded
    result = await service.retrieve(OrchestrationRequest(question="test"), route, None)
    assert isinstance(result, EvidenceBundle)


@pytest.mark.asyncio
async def test_require_minimum_count_policy():
    """RequireMinimumCountPolicy enforces minimum successful retrievers."""

    async def failing_vector(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("Vector failed")

    async def succeeding_bm25(*_args, **_kwargs) -> EvidenceBundle:
        return EvidenceBundle()

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    # Require at least 2 successful retrievers
    policy = RequireMinimumCountPolicy(minimum_successful=2)
    service = RAGAgentService(
        vector=failing_vector,
        bm25=succeeding_bm25,
        degradation_policy=policy
    )

    # Should fail because only 1 succeeded (bm25), but policy requires 2
    with pytest.raises(RetrievalFailureError) as exc_info:
        await service.retrieve(OrchestrationRequest(question="test"), route, None)

    assert exc_info.value.successful_attempts == 1
    assert exc_info.value.total_attempts == 2


@pytest.mark.asyncio
async def test_require_specific_retriever_policy():
    """RequireSpecificRetrieverPolicy enforces specific retrievers must succeed."""

    async def failing_vector(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("Vector failed")

    async def succeeding_bm25(*_args, **_kwargs) -> EvidenceBundle:
        return EvidenceBundle()

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    # Require vector to succeed
    policy = RequireSpecificRetrieverPolicy(required_retrievers={"vector"})
    service = RAGAgentService(
        vector=failing_vector,
        bm25=succeeding_bm25,
        degradation_policy=policy
    )

    # Should fail because vector (required) failed, even though bm25 succeeded
    with pytest.raises(RetrievalFailureError) as exc_info:
        await service.retrieve(OrchestrationRequest(question="test"), route, None)

    assert "vector" in exc_info.value.failed_retrievers


@pytest.mark.asyncio
async def test_require_specific_retriever_policy_success():
    """RequireSpecificRetrieverPolicy allows success when required retrievers succeed."""

    async def succeeding_vector(*_args, **_kwargs) -> EvidenceBundle:
        return EvidenceBundle()

    async def failing_bm25(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("BM25 failed")

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    # Require vector to succeed
    policy = RequireSpecificRetrieverPolicy(required_retrievers={"vector"})
    service = RAGAgentService(
        vector=succeeding_vector,
        bm25=failing_bm25,
        degradation_policy=policy
    )

    # Should succeed because vector (required) succeeded, even though bm25 failed
    result = await service.retrieve(OrchestrationRequest(question="test"), route, None)
    assert isinstance(result, EvidenceBundle)
