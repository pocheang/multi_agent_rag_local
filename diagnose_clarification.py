"""Test script to diagnose why clarification is not triggered."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext
from app.orchestration.request import OrchestrationRequest, RequestScope


async def diagnose_clarification_issue():
    """Diagnose why clarification might not trigger."""
    print("\n" + "="*80)
    print("诊断：为什么澄清功能没有触发")
    print("="*80)

    service = EnhancedRouterService()

    # Test different questions
    test_cases = [
        ("我想设计一个RAG系统", "应该触发7轮澄清"),
        ("帮我设计RAG", "简短版本，应该也触发"),
        ("如何设计一个企业级RAG检索增强生成系统，需要支持PDF文档，数据量50GB左右，要求快速响应", "太详细，可能不触发"),
        ("RAG是什么", "简单查询，不触发"),
    ]

    for question, expected in test_cases:
        print(f"\n{'='*80}")
        print(f"测试问题: {question}")
        print(f"预期: {expected}")
        print(f"{'='*80}")

        request = OrchestrationRequest(
            question=question,
            session_id="test",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        decision = await service.route(request, clarification_context=None)

        print(f"✓ Action: {decision.action.value}")
        print(f"✓ Intent: {decision.context.intent}")
        print(f"✓ Max rounds: {decision.context.max_rounds}")

        if decision.action.value == "NEED_CLARIFICATION":
            print(f"✅ 触发澄清")
            if decision.clarification:
                print(f"   问题: {decision.clarification.question}")
                print(f"   字段: {decision.clarification.field_name}")
        else:
            print(f"❌ 没有触发澄清")
            print(f"   原因: {decision.reason}")

        # Check _is_simple_query logic
        is_simple = service._is_simple_query(question, decision.context.intent)
        print(f"✓ Is simple query: {is_simple}")

        if decision.context.intent in ["rag_design", "document_comparison"]:
            extracted = service._extract_info_from_history(question, "")
            missing = service._check_missing_info(decision.context.intent, extracted)
            print(f"✓ Extracted info: {extracted}")
            print(f"✓ Missing fields: {missing}")


if __name__ == "__main__":
    asyncio.run(diagnose_clarification_issue())
