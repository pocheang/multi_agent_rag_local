"""Test to verify total_retrievers calculation issue."""

import pytest

from app.agents.rag.service import RAGAgentService, RetrievalFailureError
from app.domain.contracts import EvidenceBundle, PlannedTask, RouteDecision, TaskBudget, TaskPlan
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_total_retrievers_count_with_plan_budget_limit():
    """Verify error message shows correct count when plan limits retrievers."""

    async def failing_vector(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("Vector failed")

    async def failing_bm25(*_args, **_kwargs) -> EvidenceBundle:
        raise RuntimeError("BM25 failed")

    # Plan that limits to only 1 retriever
    plan = TaskPlan(
        tasks=(
            PlannedTask(
                task_id="retrieve",
                prompt="query",
                retrieval_required=True,
                budget=TaskBudget(max_retrievals=1)  # Only 1 retriever!
            ),
        )
    )

    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=True,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )

    service = RAGAgentService(vector=failing_vector, bm25=failing_bm25)

    try:
        await service.retrieve(OrchestrationRequest(question="test"), route, plan)
        pytest.fail("Should have raised RetrievalFailureError")
    except RetrievalFailureError as e:
        error_msg = str(e)
        print(f"\nError message: {error_msg}")

        # The bug: it will say "All 2 retrieval attempts failed"
        # But actually only 1 retriever was attempted (due to max_retrievals=1)

        # Check what the message actually says
        if "All 2 retrieval attempts failed" in error_msg:
            print("❌ BUG CONFIRMED: Message says '2 attempts' but only 1 was actually run!")
            print("   This is because total_retrievers = len(retrievers) instead of len(jobs)")
        elif "All 1 retrieval" in error_msg or "1 retrieval attempt" in error_msg:
            print("✅ CORRECT: Message accurately reports 1 attempt")
        else:
            print(f"⚠️ UNCLEAR: Message format unexpected: {error_msg}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_total_retrievers_count_with_plan_budget_limit())
