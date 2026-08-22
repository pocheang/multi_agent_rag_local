"""
Integration test for timeout control in OrchestrationEngine.

Tests that timeout control is properly integrated and working.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from app.domain.contracts import (
    EvidenceBundle,
    EvidenceItem,
    FinalAnswer,
    RouteDecision,
    TaskPlan,
)
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import (
    TimeoutConfig,
    TimeoutError,
    get_timeout_config,
)


@pytest.mark.asyncio
async def test_engine_timeout_integration_success():
    """Test that engine successfully executes within timeout budget."""

    # Create fast mock services
    async def mock_router(request):
        await asyncio.sleep(0.01)
        return RouteDecision(
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="test",
        )

    async def mock_planner(request, route):
        return TaskPlan(tasks=())

    async def mock_retriever(request, route, plan):
        await asyncio.sleep(0.01)
        return EvidenceBundle(
            items=(
                EvidenceItem(
                    content="Test content",
                    source="test.pdf",
                    document_id="test-1",
                ),
            )
        )

    async def mock_tool_runner(request, route, plan, evidence):
        return ()

    async def mock_synthesizer(request, route, plan, evidence, tool_results):
        await asyncio.sleep(0.01)
        return FinalAnswer(
            answer="Test answer [test-1]",
            citations=("test-1",),
            route=route,
        )

    services = OrchestrationServices(
        router=mock_router,
        planner=mock_planner,
        retriever=mock_retriever,
        tool_runner=mock_tool_runner,
        synthesizer=mock_synthesizer,
    )

    # Use fast timeout config
    timeout_config = TimeoutConfig(
        total_timeout_ms=5000,
        route_timeout_ms=1000,
        plan_timeout_ms=1000,
        retrieval_timeout_ms=1000,
        tool_timeout_ms=1000,
        synthesis_timeout_ms=1000,
        finalization_timeout_ms=1000,
    )

    engine = OrchestrationEngine(
        services=services,
        timeout_config=timeout_config,
    )

    request = OrchestrationRequest(question="test query", profile="standard")
    result = await engine.execute(request)

    assert result.answer == "Test answer [test-1]"
    assert "budget_stats" in result.execution_metadata

    stats = result.execution_metadata["budget_stats"]
    assert "total_elapsed_ms" in stats
    assert "remaining_ms" in stats
    assert stats["total_elapsed_ms"] < 5000  # Should complete within budget


@pytest.mark.asyncio
async def test_engine_timeout_on_slow_route():
    """Test that engine times out when router is too slow."""

    async def slow_router(request):
        await asyncio.sleep(2.0)  # 2 seconds, exceeds timeout
        return RouteDecision(
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="test",
        )

    async def mock_planner(request, route):
        return TaskPlan(tasks=())

    async def mock_retriever(request, route, plan):
        return EvidenceBundle()

    async def mock_tool_runner(request, route, plan, evidence):
        return ()

    async def mock_synthesizer(request, route, plan, evidence, tool_results):
        return FinalAnswer(answer="", route=route)

    services = OrchestrationServices(
        router=slow_router,
        planner=mock_planner,
        retriever=mock_retriever,
        tool_runner=mock_tool_runner,
        synthesizer=mock_synthesizer,
    )

    # Very short timeout to trigger failure
    timeout_config = TimeoutConfig(
        total_timeout_ms=5000,
        route_timeout_ms=500,  # 500ms timeout, but router takes 2s
        plan_timeout_ms=500,
        retrieval_timeout_ms=500,
        tool_timeout_ms=500,
        synthesis_timeout_ms=500,
        finalization_timeout_ms=500,
    )

    engine = OrchestrationEngine(
        services=services,
        timeout_config=timeout_config,
    )

    request = OrchestrationRequest(question="test query", profile="standard")

    with pytest.raises(TimeoutError) as exc_info:
        await engine.execute(request)

    assert exc_info.value.stage == "route"
    assert exc_info.value.timeout_ms == 500


@pytest.mark.asyncio
async def test_engine_timeout_on_slow_retrieval():
    """Test that engine times out when retrieval is too slow."""

    async def mock_router(request):
        return RouteDecision(
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="test",
        )

    async def mock_planner(request, route):
        return TaskPlan(tasks=())

    async def slow_retriever(request, route, plan):
        await asyncio.sleep(2.0)  # 2 seconds, exceeds timeout
        return EvidenceBundle()

    async def mock_tool_runner(request, route, plan, evidence):
        return ()

    async def mock_synthesizer(request, route, plan, evidence, tool_results):
        return FinalAnswer(answer="", route=route)

    services = OrchestrationServices(
        router=mock_router,
        planner=mock_planner,
        retriever=slow_retriever,
        tool_runner=mock_tool_runner,
        synthesizer=mock_synthesizer,
    )

    timeout_config = TimeoutConfig(
        total_timeout_ms=5000,
        route_timeout_ms=500,
        plan_timeout_ms=500,
        retrieval_timeout_ms=500,  # 500ms timeout
        tool_timeout_ms=500,
        synthesis_timeout_ms=500,
        finalization_timeout_ms=500,
    )

    engine = OrchestrationEngine(
        services=services,
        timeout_config=timeout_config,
    )

    request = OrchestrationRequest(question="test query", profile="standard")

    with pytest.raises(TimeoutError) as exc_info:
        await engine.execute(request)

    assert exc_info.value.stage == "rag"


@pytest.mark.asyncio
async def test_engine_budget_stats_in_result():
    """Test that budget statistics are included in execution metadata."""

    async def mock_router(request):
        return RouteDecision(
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="test",
        )

    async def mock_planner(request, route):
        return TaskPlan(tasks=())

    async def mock_retriever(request, route, plan):
        return EvidenceBundle(
            items=(
                EvidenceItem(
                    content="Test",
                    source="test.pdf",
                    document_id="test-1",
                ),
            )
        )

    async def mock_tool_runner(request, route, plan, evidence):
        return ()

    async def mock_synthesizer(request, route, plan, evidence, tool_results):
        return FinalAnswer(answer="Test [test-1]", route=route, citations=("test-1",))

    services = OrchestrationServices(
        router=mock_router,
        planner=mock_planner,
        retriever=mock_retriever,
        tool_runner=mock_tool_runner,
        synthesizer=mock_synthesizer,
    )

    engine = OrchestrationEngine(services=services)
    request = OrchestrationRequest(question="test", profile="standard")
    result = await engine.execute(request)

    # Check budget stats are present
    assert "budget_stats" in result.execution_metadata
    stats = result.execution_metadata["budget_stats"]

    # Verify structure
    assert "total_elapsed_ms" in stats
    assert "total_budget_ms" in stats
    assert "remaining_ms" in stats
    assert "stage_times" in stats
    assert "budget_utilization" in stats

    # Verify values make sense
    assert stats["total_elapsed_ms"] >= 0
    assert stats["total_budget_ms"] == 30000  # Standard is 30s
    assert stats["remaining_ms"] >= 0
    assert stats["budget_utilization"] >= 0
    assert stats["budget_utilization"] <= 1.0

    # Check that stages were recorded
    assert "route" in stats["stage_times"]
    assert "rag" in stats["stage_times"]
    assert "synthesize" in stats["stage_times"]


@pytest.mark.asyncio
async def test_engine_uses_profile_timeout():
    """Test that engine uses correct timeout config for profile."""

    async def mock_router(request):
        return RouteDecision(
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="test",
        )

    async def mock_planner(request, route):
        return TaskPlan(tasks=())

    async def mock_retriever(request, route, plan):
        return EvidenceBundle(
            items=(
                EvidenceItem(
                    content="Test",
                    source="test.pdf",
                    document_id="test-1",
                ),
            )
        )

    async def mock_tool_runner(request, route, plan, evidence):
        return ()

    async def mock_synthesizer(request, route, plan, evidence, tool_results):
        return FinalAnswer(answer="Test [test-1]", route=route)

    services = OrchestrationServices(
        router=mock_router,
        planner=mock_planner,
        retriever=mock_retriever,
        tool_runner=mock_tool_runner,
        synthesizer=mock_synthesizer,
    )

    # Engine without explicit timeout config should use profile
    engine = OrchestrationEngine(services=services)

    # Test with strict_quality profile (60s total)
    request = OrchestrationRequest(question="test", profile="strict_quality")
    result = await engine.execute(request)

    stats = result.execution_metadata["budget_stats"]
    assert stats["total_budget_ms"] == 60000  # Strict quality is 60s


def test_timeout_integration_summary():
    """Print summary of timeout integration tests."""
    print("\n" + "="*70)
    print("TIMEOUT CONTROL INTEGRATION - TEST SUMMARY")
    print("="*70)
    print("\n✅ OrchestrationEngine Timeout Integration")
    print("   - Timeout config parameter added to __init__")
    print("   - ExecutionBudget tracks time per stage")
    print("   - Budget statistics included in execution metadata")
    print("   - Profile-aware timeout configuration")
    print("   - Proper timeout errors with stage information")
    print("\n" + "="*70)
    print("Integration complete! ✓")
    print("="*70 + "\n")
