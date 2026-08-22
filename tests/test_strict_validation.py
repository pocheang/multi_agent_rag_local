"""Tests for strict validation and edge cases."""

import pytest
import warnings

from app.agents.rag.service import (
    RAGAgentService,
    RequireMinimumCountPolicy,
    RequireSpecificRetrieverPolicy,
    RetrievalFailureError,
)
from app.domain.contracts import EvidenceBundle, RouteDecision
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_retrieval_failure_error_message_with_all_failures():
    """Verify error message is accurate when all retrievers fail."""

    async def failing_vector(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("Vector failed")

    async def failing_bm25(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("BM25 failed")

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    service = RAGAgentService(vector=failing_vector, bm25=failing_bm25)

    with pytest.raises(RetrievalFailureError) as exc_info:
        await service.retrieve(OrchestrationRequest(question="test"), route, None)

    error = exc_info.value
    assert error.successful_attempts == 0
    assert error.total_attempts == 2
    assert error.failed_retrievers == {"vector", "bm25"}
    # Message should say "All 2 attempts failed"
    assert "All 2 retrieval attempts failed" in str(error)


@pytest.mark.asyncio
async def test_retrieval_failure_error_message_with_partial_success():
    """Verify error message is accurate when some succeed but policy requires more."""

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

    # Require 2 successful, but only 1 will succeed
    policy = RequireMinimumCountPolicy(minimum_successful=2)
    service = RAGAgentService(
        vector=succeeding_vector,
        bm25=failing_bm25,
        degradation_policy=policy
    )

    with pytest.raises(RetrievalFailureError) as exc_info:
        await service.retrieve(OrchestrationRequest(question="test"), route, None)

    error = exc_info.value
    assert error.successful_attempts == 1
    assert error.total_attempts == 2
    assert error.failed_retrievers == {"bm25"}
    # Message should say "1/2 successful" not "All 2 failed"
    assert "Degradation policy violation" in str(error)
    assert "1/2 successful attempts" in str(error)
    assert "All 2" not in str(error)  # Should NOT say "All 2 failed"


def test_retriever_timeout_validation_negative():
    """Verify negative timeout is rejected."""
    with pytest.raises(ValueError, match="retriever_timeout must be positive"):
        RAGAgentService(retriever_timeout=-1)


def test_retriever_timeout_validation_zero():
    """Verify zero timeout is rejected."""
    with pytest.raises(ValueError, match="retriever_timeout must be positive"):
        RAGAgentService(retriever_timeout=0)


def test_retriever_timeout_validation_large():
    """Verify large timeout triggers warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        RAGAgentService(retriever_timeout=400)
        assert len(w) == 1
        assert "very large" in str(w[0].message)


def test_require_minimum_count_policy_validation_negative():
    """Verify negative minimum_successful is rejected."""
    with pytest.raises(ValueError, match="minimum_successful must be >= 1"):
        RequireMinimumCountPolicy(minimum_successful=-1)


def test_require_minimum_count_policy_validation_zero():
    """Verify zero minimum_successful is rejected."""
    with pytest.raises(ValueError, match="minimum_successful must be >= 1"):
        RequireMinimumCountPolicy(minimum_successful=0)


def test_require_specific_retriever_policy_validation_empty():
    """Verify empty required_retrievers is rejected."""
    with pytest.raises(ValueError, match="required_retrievers cannot be empty"):
        RequireSpecificRetrieverPolicy(required_retrievers=set())


def test_require_specific_retriever_policy_validation_unknown_names():
    """Verify unknown retriever names trigger warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        RequireSpecificRetrieverPolicy(required_retrievers={"vector", "unknown", "invalid"})
        assert len(w) == 1
        assert "Unknown retriever names" in str(w[0].message)
        assert "unknown" in str(w[0].message)
        assert "invalid" in str(w[0].message)


def test_require_specific_retriever_policy_validation_valid_names():
    """Verify valid retriever names do not trigger warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        RequireSpecificRetrieverPolicy(required_retrievers={"vector", "bm25"})
        assert len(w) == 0  # No warnings


@pytest.mark.asyncio
async def test_error_message_sorted_retrievers():
    """Verify failed retriever names are sorted in error messages."""

    async def failing(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("Failed")

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    service = RAGAgentService(vector=failing, bm25=failing)

    with pytest.raises(RetrievalFailureError) as exc_info:
        await service.retrieve(OrchestrationRequest(question="test"), route, None)

    error_msg = str(exc_info.value)
    # Names should be sorted: bm25 before vector
    assert "bm25" in error_msg
    assert "vector" in error_msg
    # Check they're sorted (bm25 should appear before vector)
    bm25_pos = error_msg.index("bm25")
    vector_pos = error_msg.index("vector")
    assert bm25_pos < vector_pos
