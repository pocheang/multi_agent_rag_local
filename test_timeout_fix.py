"""Test the timeout fix for clarification endpoint."""

import asyncio
import time
from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext
from app.orchestration.request import OrchestrationRequest, RequestScope


async def test_performance():
    """Test clarification check performance."""
    print("=== Testing Clarification Performance ===\n")

    service = EnhancedRouterService()

    # Test question that should trigger clarification
    question = "我想设计一个RAG系统"

    request = OrchestrationRequest(
        question=question,
        session_id="test_session",
        conversation=tuple(),
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()

    # Measure time
    start = time.time()
    print(f"Testing: {question}")
    print(f"Starting at: {time.strftime('%H:%M:%S')}")

    decision = await service.route(request, context)

    elapsed = time.time() - start
    print(f"\n✅ Completed in {elapsed:.2f} seconds")

    if elapsed > 30:
        print("⚠️  WARNING: Response took longer than 30 seconds!")
        print("   This would have timed out with the old frontend timeout.")
    else:
        print("✅ Response time is acceptable (< 30 seconds)")

    print(f"\nAction: {decision.action}")
    print(f"Intent: {decision.intent}")

    if decision.clarification:
        print(f"Clarification question: {decision.clarification.question}")
        print(f"Field name: {decision.clarification.field_name}")

    print("\n=== Performance Test Complete ===")

    # Performance analysis
    print("\n=== Analysis ===")
    if elapsed < 5:
        print("✅ EXCELLENT: Response < 5 seconds")
    elif elapsed < 15:
        print("✅ GOOD: Response < 15 seconds")
    elif elapsed < 30:
        print("⚠️  ACCEPTABLE: Response < 30 seconds but could be faster")
    else:
        print("❌ PROBLEM: Response > 30 seconds, needs optimization")


if __name__ == "__main__":
    asyncio.run(test_performance())
