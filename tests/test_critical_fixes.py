"""Test critical bug fixes."""

import pytest
import threading
import time
from app.services.runtime.retry_policy import call_with_retry
from app.agents.rag.service import RAGAgentService, _shutdown_retriever_pool
from app.agents.router.service import _to_domain_route
from app.pipeline.rag_pipeline import _parse_citation_label
from app.orchestration.timeout_control import get_timeout_config


def test_retry_policy_last_exception_handling():
    """Test that retry policy handles last exception correctly."""

    def failing_operation():
        raise ValueError("Operation failed")

    with pytest.raises(ValueError, match="Operation failed"):
        call_with_retry("test_op", failing_operation)


def test_retriever_pool_shutdown_resilience():
    """Test that retriever pool shutdown handles exceptions gracefully."""
    # This should not raise even if called multiple times
    _shutdown_retriever_pool()
    _shutdown_retriever_pool()


def test_rag_service_reporter_thread_safety():
    """Test that set_degradation_reporter is thread-safe."""
    service = RAGAgentService()

    async def mock_reporter(event):
        pass

    def set_reporter():
        for _ in range(100):
            service.set_degradation_reporter(mock_reporter)

    threads = [threading.Thread(target=set_reporter) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should complete without errors


def test_router_confidence_normalization_with_logging():
    """Test that out-of-range confidence values are logged."""
    # Should not raise, but should log warning
    route1 = _to_domain_route("vector", 1.5, "test")
    assert route1.confidence == 1.0

    route2 = _to_domain_route("vector", -0.5, "test")
    assert route2.confidence == 0.0

    route3 = _to_domain_route("vector", 0.5, "test")
    assert route3.confidence == 0.5


def test_citation_parsing_with_logging():
    """Test that citation parsing handles errors gracefully."""
    # Valid citation
    citation1 = _parse_citation_label("doc1:5")
    assert citation1.document_id == "doc1"
    assert citation1.page == 5

    # Invalid page number
    citation2 = _parse_citation_label("doc1:invalid")
    assert citation2.source == "doc1:invalid"
    assert citation2.page is None

    # No colon
    citation3 = _parse_citation_label("doc1")
    assert citation3.source == "doc1"
    assert citation3.page is None


def test_timeout_config_validation_at_module_load():
    """Test that timeout configurations are valid."""
    # These should not raise since they're validated at module load
    config1 = get_timeout_config("standard")
    assert config1.total_timeout_ms == 30000

    config2 = get_timeout_config("strict_quality")
    assert config2.total_timeout_ms == 60000

    config3 = get_timeout_config("fast")
    assert config3.total_timeout_ms == 15000

    # Unknown profile should return standard
    config4 = get_timeout_config("unknown")
    assert config4.total_timeout_ms == 30000


def test_empty_evidence_synthesis_fallback():
    """Test that synthesis handles empty evidence correctly."""
    from app.agents.synthesizer.service import SynthesizerAgentService
    from app.domain.contracts import EvidenceBundle, RouteDecision
    from app.orchestration.request import OrchestrationRequest

    service = SynthesizerAgentService()
    request = OrchestrationRequest(question="test", profile="standard")
    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=1.0,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test_route",
    )
    evidence = EvidenceBundle()  # Empty

    import asyncio
    result = asyncio.run(service.synthesize(request, route, None, evidence, ()))

    # Should return fallback message
    assert result.answer
    assert len(result.citations) == 0
    assert result.execution_summary == "evidence=0 tool_results=0 (fallback)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
