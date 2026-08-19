"""
Hybrid Clarification System - Usage Examples and Tests
混合澄清系统 - 使用示例和测试
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def example_1_rule_based_fast_path():
    """示例1: 规则模式（快速路径）"""
    print("\n" + "=" * 60)
    print("示例1: 规则模式 - 常见意图识别")
    print("=" * 60)

    from app.agents.router.hybrid_clarification import HybridClarificationService

    service = HybridClarificationService(enable_llm_fallback=False)

    # 测试RAG设计意图
    question = "我想设计一个RAG知识库系统"
    intent, confidence = await service.identify_intent(question, {})

    print(f"问题: {question}")
    print(f"识别意图: {intent}")
    print(f"置信度: {confidence:.2f}")
    print(f"方法: 规则匹配（无LLM调用）")


async def example_2_hybrid_mode():
    """示例2: 混合模式 - 规则优先，LLM fallback"""
    print("\n" + "=" * 60)
    print("示例2: 混合模式 - 边界case使用LLM")
    print("=" * 60)

    from app.agents.router.hybrid_clarification import HybridClarificationService

    service = HybridClarificationService(enable_llm_fallback=True)

    test_cases = [
        ("如何设计一个RAG系统", "预期: 规则匹配"),
        ("我需要一个可以处理多种文档格式的智能检索方案", "预期: LLM理解"),
    ]

    for question, expected in test_cases:
        print(f"\n问题: {question}")
        print(f"{expected}")

        intent, confidence = await service.identify_intent(question, {})
        print(f"识别意图: {intent}")
        print(f"置信度: {confidence:.2f}")


async def example_3_info_extraction():
    """示例3: 信息提取 - 规则 + LLM增强"""
    print("\n" + "=" * 60)
    print("示例3: 混合信息提取")
    print("=" * 60)

    from app.agents.router.hybrid_clarification import HybridClarificationService

    service = HybridClarificationService(enable_llm_fallback=True)

    question = "我想搭建一个企业知识库"
    context = """
    用户: 我们公司有大约50GB的PDF文档
    助手: 了解，请问对性能有什么要求？
    用户: 希望能在2秒内返回结果
    """

    fields = ["scenario", "data_source", "scale", "performance_requirement"]

    # 规则提取
    print("\n--- 规则提取 ---")
    rule_result = await service.extract_info_from_context(
        question, context, fields, use_llm=False
    )
    print(f"提取结果: {rule_result}")

    # LLM增强提取
    print("\n--- LLM增强提取 ---")
    hybrid_result = await service.extract_info_from_context(
        question, context, fields, use_llm=True
    )
    print(f"提取结果: {hybrid_result}")


async def example_4_dynamic_question_generation():
    """示例4: 动态问题生成 - 处理未定义意图"""
    print("\n" + "=" * 60)
    print("示例4: LLM动态生成澄清问题")
    print("=" * 60)

    from app.agents.router.hybrid_clarification import HybridClarificationService

    service = HybridClarificationService(enable_llm_fallback=True)

    intent = "custom_intent"  # 未在规则中定义
    missing_fields = ["architecture_type"]
    known_info = {"scale": "large", "team_size": "10"}

    print(f"意图: {intent} (未定义)")
    print(f"缺失字段: {missing_fields}")
    print(f"已知信息: {known_info}")

    question = await service.generate_next_question(
        intent, missing_fields, known_info, use_llm=True
    )

    if question:
        print(f"\n生成的问题: {question.question}")
        print(f"选项: {question.options}")
        print(f"字段名: {question.field_name}")
    else:
        print("\n无法生成问题")


async def example_5_performance_comparison():
    """示例5: 性能对比 - 规则 vs LLM"""
    print("\n" + "=" * 60)
    print("示例5: 性能对比")
    print("=" * 60)

    import time
    from app.agents.router.hybrid_clarification import HybridClarificationService

    service = HybridClarificationService(enable_llm_fallback=True)
    question = "如何设计一个RAG知识库系统"

    # 规则模式
    start = time.time()
    intent_rule, conf_rule = await service.identify_intent(question, {}, use_llm=False)
    time_rule = (time.time() - start) * 1000

    # LLM模式
    start = time.time()
    intent_llm, conf_llm = await service.identify_intent(question, {}, use_llm=True)
    time_llm = (time.time() - start) * 1000

    print(f"问题: {question}\n")
    print(f"规则模式:")
    print(f"  意图: {intent_rule}, 置信度: {conf_rule:.2f}, 耗时: {time_rule:.0f}ms")
    print(f"\nLLM模式:")
    print(f"  意图: {intent_llm}, 置信度: {conf_llm:.2f}, 耗时: {time_llm:.0f}ms")
    print(f"\n速度比: {time_llm / time_rule:.1f}x (LLM较慢)")


async def test_hybrid_integration():
    """测试: 集成到EnhancedRouterService"""
    print("\n" + "=" * 60)
    print("集成测试: EnhancedRouterService with Hybrid Mode")
    print("=" * 60)

    import os

    # 临时启用混合模式
    os.environ["USE_HYBRID_CLARIFICATION"] = "false"  # 默认关闭

    from app.agents.router.enhanced_service import EnhancedRouterService

    service = EnhancedRouterService()

    print(f"混合模式: {service.hybrid_service is not None}")
    print("\n提示: 设置环境变量启用混合模式:")
    print("  export USE_HYBRID_CLARIFICATION=true")
    print("  export LLM_FALLBACK_THRESHOLD=0.8")


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("混合澄清系统 - 示例演示")
    print("=" * 60)

    examples = [
        ("规则模式", example_1_rule_based_fast_path),
        ("混合模式", example_2_hybrid_mode),
        ("信息提取", example_3_info_extraction),
        ("动态问题生成", example_4_dynamic_question_generation),
        ("性能对比", example_5_performance_comparison),
        ("集成测试", test_hybrid_integration),
    ]

    for name, func in examples:
        try:
            await func()
        except Exception as e:
            print(f"\n[错误] {name}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
