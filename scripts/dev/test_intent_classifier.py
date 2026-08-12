"""
测试LLM意图分类器的准确性。
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.query.intent_classifier import classify_intent_with_llm
from app.services.agent_classifier import classify_agent_class


def test_intent_classification():
    """测试不同类型的问题。"""
    test_cases = [
        # 网络安全相关
        ("什么是SQL注入攻击？", "cybersecurity"),
        ("如何防护XSS漏洞？", "cybersecurity"),
        ("介绍一下零信任架构", "cybersecurity"),

        # AI相关
        ("什么是Transformer模型？", "artificial_intelligence"),
        ("如何训练神经网络？", "artificial_intelligence"),
        ("介绍一下深度学习", "artificial_intelligence"),

        # PDF相关
        ("帮我读取这个PDF文档", "pdf_text"),
        ("分析这个PDF的内容", "pdf_text"),

        # 通用知识
        ("给我介绍一下有哪些知识", "general"),
        ("你好", "general"),
        ("今天天气怎么样", "general"),
    ]

    print("=" * 80)
    print("LLM意图分类器测试")
    print("=" * 80)

    correct_llm = 0
    correct_rule = 0
    total = len(test_cases)

    for question, expected in test_cases:
        print(f"\n问题: {question}")
        print(f"期望类别: {expected}")

        # LLM分类
        llm_result = classify_intent_with_llm(question)
        llm_class = llm_result["agent_class"]
        llm_confidence = llm_result["confidence"]
        llm_method = llm_result["method"]
        llm_reason = llm_result["reason"]

        # 规则分类
        rule_class = classify_agent_class(question)

        print(f"LLM分类: {llm_class} (置信度: {llm_confidence:.2f}, 方法: {llm_method})")
        print(f"理由: {llm_reason}")
        print(f"规则分类: {rule_class}")

        if llm_class == expected:
            correct_llm += 1
            print("✓ LLM分类正确")
        else:
            print("✗ LLM分类错误")

        if rule_class == expected:
            correct_rule += 1
            print("✓ 规则分类正确")
        else:
            print("✗ 规则分类错误")

    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"LLM分类准确率: {correct_llm}/{total} ({correct_llm/total*100:.1f}%)")
    print(f"规则分类准确率: {correct_rule}/{total} ({correct_rule/total*100:.1f}%)")
    print(f"LLM改进: {(correct_llm - correct_rule)/total*100:+.1f}%")


if __name__ == "__main__":
    test_intent_classification()
