"""Test multi-round clarification workflow end-to-end."""

import asyncio
from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext
from app.orchestration.request import OrchestrationRequest, RequestScope


async def simulate_multi_round_clarification():
    """Simulate a complete multi-round clarification session."""
    print("=== Multi-Round Clarification Test ===\n")

    service = EnhancedRouterService()
    question = "我想设计一个RAG系统"

    # Round 1: Initial question
    print("Round 1: Initial question")
    print(f"Question: {question}\n")

    request = OrchestrationRequest(
        question=question,
        session_id="test_session",
        conversation=tuple(),
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    print(f"Action: {decision.action}")
    print(f"Intent: {decision.intent}")
    if decision.clarification:
        print(f"Question: {decision.clarification.question}")
        print(f"Field: {decision.clarification.field_name}")
        print(f"Options: {decision.clarification.options}\n")

    assert decision.action.value == "NEED_CLARIFICATION", "Should need clarification"
    assert decision.clarification is not None, "Should have clarification question"

    # Simulate answers for up to 7 rounds
    answers = {
        "scenario": "企业知识库",
        "data_source": "PDF文档",
        "data_volume": "中等规模",
        "performance_requirement": "快速",
        "accuracy_requirement": "高精度",
        "deployment_env": "云端",
        "budget": "充足",
    }

    collected = {}
    round_num = 1

    while decision.action.value == "NEED_CLARIFICATION" and round_num <= 10:
        round_num += 1
        print(f"\nRound {round_num}: User answers")

        field_name = decision.clarification.field_name
        answer = answers.get(field_name, "其他")
        print(f"User answers '{field_name}': {answer}")

        # Update context
        collected[field_name] = answer
        context = ClarificationContext(
            collected_info=collected,
            asked_questions=[field_name],
            clarification_round=round_num - 1,
            max_rounds=decision.context.max_rounds,
            intent=decision.context.intent,
        )

        # Next round
        decision = await service.route(request, context)
        print(f"Action: {decision.action}")

        if decision.action.value == "NEED_CLARIFICATION" and decision.clarification:
            print(f"Next question: {decision.clarification.question}")
            print(f"Next field: {decision.clarification.field_name}")
        else:
            print(f"✅ Clarification complete!")
            print(f"Final intent: {decision.intent}")
            print(f"Final route: {decision.route}")
            print(f"Collected info: {collected}")
            break

    print(f"\n=== Test Complete ===")
    print(f"Total rounds: {round_num}")
    print(f"Final action: {decision.action}")
    print(f"Information collected: {len(collected)} fields")

    # Verify
    assert decision.action.value == "CONTINUE", "Should eventually reach CONTINUE"
    assert len(collected) > 0, "Should have collected some information"
    print("\n✅ All assertions passed!")


if __name__ == "__main__":
    asyncio.run(simulate_multi_round_clarification())
