"""Quick validation script for clarification flow with dynamic rounds.

Usage:
    python scripts/test_clarification_flow.py
"""

import asyncio
from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext, RouterAction
from app.orchestration.request import OrchestrationRequest, RequestScope


async def test_simple_query():
    """Test: Simple query (2 rounds max)."""
    print("\n" + "="*60)
    print("Test 1: Simple Query (Expected: 2 rounds max)")
    print("="*60)

    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="这个产品的价格是多少？",
        session_id="test_simple",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    print(f"Question: {request.question}")
    print(f"Intent: {decision.context.intent}")
    print(f"Max Rounds: {decision.context.max_rounds}")
    print(f"Action: {decision.action}")
    print(f"✓ PASS" if decision.action == RouterAction.CONTINUE else "✗ FAIL")


async def test_rag_design():
    """Test: RAG design (7 rounds max)."""
    print("\n" + "="*60)
    print("Test 2: RAG Design (Expected: 7 rounds max)")
    print("="*60)

    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="帮我设计一个RAG检索增强生成系统",
        session_id="test_rag",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    print(f"Question: {request.question}")
    print(f"Intent: {decision.context.intent}")
    print(f"Max Rounds: {decision.context.max_rounds}")
    print(f"Action: {decision.action}")

    if decision.action == RouterAction.NEED_CLARIFICATION:
        print(f"\nClarification Question: {decision.clarification.question}")
        print(f"Options: {decision.clarification.options}")

    expected = decision.context.intent == "rag_design" and decision.context.max_rounds == 7
    print(f"✓ PASS" if expected else "✗ FAIL")


async def test_document_comparison():
    """Test: Document comparison (5 rounds max)."""
    print("\n" + "="*60)
    print("Test 3: Document Comparison (Expected: 5 rounds max)")
    print("="*60)

    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="比较产品A和产品B的差异",
        session_id="test_comparison",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    print(f"Question: {request.question}")
    print(f"Intent: {decision.context.intent}")
    print(f"Max Rounds: {decision.context.max_rounds}")
    print(f"Action: {decision.action}")

    if decision.action == RouterAction.NEED_CLARIFICATION:
        print(f"\nClarification Question: {decision.clarification.question}")
        print(f"Field Name: {decision.clarification.field_name}")

    expected = decision.context.intent == "document_comparison" and decision.context.max_rounds == 5
    print(f"✓ PASS" if expected else "✗ FAIL")


async def test_intent_change():
    """Test: Intent change updates max_rounds."""
    print("\n" + "="*60)
    print("Test 4: Intent Change (Expected: max_rounds updates)")
    print("="*60)

    service = EnhancedRouterService()

    # First query: document comparison (5 rounds)
    request1 = OrchestrationRequest(
        question="比较两个产品",
        session_id="test_change",
        use_reasoning=False,
        source_scope=RequestScope(),
    )
    context = ClarificationContext()
    decision1 = await service.route(request1, context)

    print(f"Query 1: {request1.question}")
    print(f"Intent: {decision1.context.intent}")
    print(f"Max Rounds: {decision1.context.max_rounds}")

    # Second query: RAG design (7 rounds)
    request2 = OrchestrationRequest(
        question="其实我想设计一个RAG系统",
        session_id="test_change",
        use_reasoning=False,
        source_scope=RequestScope(),
    )
    context = decision1.context
    context.clarification_round = 2  # Simulate 2 rounds used
    decision2 = await service.route(request2, context)

    print(f"\nQuery 2: {request2.question}")
    print(f"Intent: {decision2.context.intent}")
    print(f"Max Rounds: {decision2.context.max_rounds}")

    expected = (
        decision1.context.max_rounds == 5 and
        decision2.context.max_rounds == 7
    )
    print(f"✓ PASS" if expected else "✗ FAIL")


async def test_max_rounds_enforcement():
    """Test: Max rounds enforcement."""
    print("\n" + "="*60)
    print("Test 5: Max Rounds Enforcement (Expected: CONTINUE when exceeded)")
    print("="*60)

    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="设计RAG",
        session_id="test_enforce",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    # Simulate reaching max rounds
    context = ClarificationContext(
        intent="rag_design",
        max_rounds=7,
        clarification_round=7,  # Reached limit
    )

    decision = await service.route(request, context)

    print(f"Question: {request.question}")
    print(f"Intent: {decision.context.intent}")
    print(f"Current Round: {decision.context.clarification_round}")
    print(f"Max Rounds: {decision.context.max_rounds}")
    print(f"Action: {decision.action}")

    expected = decision.action == RouterAction.CONTINUE
    print(f"✓ PASS (Forced CONTINUE)" if expected else "✗ FAIL")


async def test_multi_round_flow():
    """Test: Multi-round clarification flow."""
    print("\n" + "="*60)
    print("Test 6: Multi-Round Flow (RAG Design with answers)")
    print("="*60)

    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="设计RAG系统",
        session_id="test_multi",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()

    # Round 1
    decision1 = await service.route(request, context)
    print(f"\nRound 1:")
    print(f"  Intent: {decision1.context.intent}")
    print(f"  Max Rounds: {decision1.context.max_rounds}")
    print(f"  Action: {decision1.action}")
    if decision1.clarification:
        print(f"  Question: {decision1.clarification.question}")

    # Simulate user answer
    if decision1.action == RouterAction.NEED_CLARIFICATION and decision1.clarification:
        context = decision1.context
        context.collected_info[decision1.clarification.field_name] = "企业知识库"
        context.asked_questions.append(decision1.clarification.field_name)
        context.clarification_round += 1

        # Round 2
        decision2 = await service.route(request, context)
        print(f"\nRound 2:")
        print(f"  Collected: {decision2.context.collected_info}")
        print(f"  Action: {decision2.action}")
        if decision2.clarification:
            print(f"  Question: {decision2.clarification.question}")

        print(f"\n✓ PASS (Multi-round flow working)")
    else:
        print(f"\n✗ FAIL (Expected NEED_CLARIFICATION)")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Enhanced Router Service - Dynamic Rounds Validation")
    print("="*60)

    await test_simple_query()
    await test_rag_design()
    await test_document_comparison()
    await test_intent_change()
    await test_max_rounds_enforcement()
    await test_multi_round_flow()

    print("\n" + "="*60)
    print("Validation Complete")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
