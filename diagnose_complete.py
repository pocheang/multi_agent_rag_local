"""Complete diagnostic script for clarification flow."""

print("""
================================================================================
澄清功能诊断 - 完整流程检查
================================================================================

可能的失效原因:
1. ❌ 用户未登录 → 401错误 → 显示认证错误（正确行为）
2. ❌ 后端判断为simple_query → 返回CONTINUE → 直接执行查询
3. ❌ Intent识别错误 → 不匹配rag_design → 不触发澄清
4. ❌ _is_simple_query()过早返回True → 跳过澄清

让我们逐一检查...
================================================================================
""")

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.router.enhanced_service import EnhancedRouterService, INTENT_REQUIRED_INFO
from app.domain.contracts import ClarificationContext
from app.orchestration.request import OrchestrationRequest, RequestScope


async def test_intent_detection():
    """Test 1: Intent detection."""
    print("\n[测试1] Intent 识别")
    print("="*80)

    service = EnhancedRouterService()
    test_questions = [
        "我想设计一个RAG系统",
        "设计RAG",
        "如何搭建RAG",
        "帮我实现一个检索增强生成系统",
    ]

    for q in test_questions:
        intent = await service._identify_intent(q, {})
        print(f"问题: {q}")
        print(f"  → Intent: {intent}")
        print(f"  → 是否需要澄清: {'是' if intent in INTENT_REQUIRED_INFO else '否'}")


async def test_simple_query_logic():
    """Test 2: Simple query detection."""
    print("\n[测试2] Simple Query 判断")
    print("="*80)

    service = EnhancedRouterService()
    test_cases = [
        ("我想设计一个RAG系统", "rag_design"),
        ("帮我设计一个企业级RAG系统，需要处理50GB的PDF文档，要求1秒响应", "rag_design"),
        ("RAG是什么", "general_query"),
    ]

    for question, intent in test_cases:
        is_simple = service._is_simple_query(question, intent)
        print(f"问题: {question}")
        print(f"  Intent: {intent}")
        print(f"  → Is simple: {is_simple} {'(会跳过澄清)' if is_simple else '(需要澄清)'}")


async def test_extraction_logic():
    """Test 3: Information extraction."""
    print("\n[测试3] 信息提取能力")
    print("="*80)

    service = EnhancedRouterService()
    test_cases = [
        "我想设计一个RAG系统",
        "我想搭建一个企业知识库",
        "需要处理50GB的PDF文档",
        "要求实时响应，1秒内返回结果",
    ]

    for question in test_cases:
        extracted = service._extract_info_from_history(question, "")
        print(f"问题: {question}")
        print(f"  → 提取到: {extracted if extracted else '(无)'}")


async def test_full_flow():
    """Test 4: Complete flow."""
    print("\n[测试4] 完整流程测试")
    print("="*80)

    service = EnhancedRouterService()
    question = "我想设计一个RAG系统"

    request = OrchestrationRequest(
        question=question,
        session_id="test",
        conversation=tuple(),
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    print(f"问题: {question}\n")

    # Step by step
    print("步骤1: 识别Intent")
    intent = await service._identify_intent(question, {})
    print(f"  → {intent}")

    print("\n步骤2: 检查是否simple_query")
    is_simple = service._is_simple_query(question, intent)
    print(f"  → {is_simple}")
    if is_simple:
        print("  ⚠️  问题: 被判断为simple_query，会跳过澄清！")

    print("\n步骤3: 提取信息")
    extracted = service._extract_info_from_history(question, "")
    print(f"  → {extracted if extracted else '(无)'}")

    print("\n步骤4: 检查缺失字段")
    if intent in INTENT_REQUIRED_INFO:
        missing = service._check_missing_info(intent, extracted)
        print(f"  → 缺失: {missing}")
        print(f"  → 需要的字段: {INTENT_REQUIRED_INFO[intent]['fields']}")

    print("\n步骤5: 执行完整route决策")
    decision = await service.route(request, None)
    print(f"  → Action: {decision.action.value}")
    print(f"  → Intent: {decision.context.intent}")

    if decision.action.value == "NEED_CLARIFICATION":
        print(f"  ✅ 成功触发澄清")
        if decision.clarification:
            print(f"  → 问题: {decision.clarification.question}")
    else:
        print(f"  ❌ 没有触发澄清!")
        print(f"  → 原因需要调查")


async def main():
    await test_intent_detection()
    await test_simple_query_logic()
    await test_extraction_logic()
    await test_full_flow()

    print("\n" + "="*80)
    print("诊断完成!")
    print("="*80)
    print("""
如果看到"没有触发澄清"，最可能的原因是:
1. _is_simple_query() 返回 True (检查测试2的结果)
2. Intent 识别错误 (检查测试1的结果)

解决方案:
- 如果是_is_simple_query问题: 调整判断逻辑
- 如果是Intent识别问题: 改进关键词匹配或使用LLM
""")


if __name__ == "__main__":
    asyncio.run(main())
