"""
Demo script for query optimization service.

Shows how the service detects and suggests improvements for various query types.
"""

from app.services.query_optimization import QueryOptimizationService


def print_analysis(query: str, service: QueryOptimizationService) -> None:
    """Print analysis results for a query."""
    print(f"\n{'=' * 80}")
    print(f"Query: {query}")
    print(f"{'=' * 80}")

    quality, suggestion = service.analyze_and_suggest(query)

    print(f"\n质量评分: {quality.score:.1f}/100")
    print(f"质量等级: {quality.level}")

    if quality.issues:
        print(f"\n检测到的问题:")
        for issue in quality.issues:
            print(f"  • {issue}")

    print(f"\n详细评分:")
    for dimension, score in quality.details.items():
        print(f"  {dimension:15s}: {score:5.1f}")

    if suggestion.clarifications:
        print(f"\n{suggestion.reasoning}")
        print(f"\n建议明确:")
        for clarification in suggestion.clarifications:
            print(f"  • {clarification}")

    if suggestion.examples:
        print(f"\n优化示例:")
        for i, example in enumerate(suggestion.examples, 1):
            print(f"  {i}. {example}")


def main():
    """Run demo scenarios."""
    service = QueryOptimizationService()

    scenarios = [
        # Very low quality
        "公司",
        "情况",
        "",

        # Low quality
        "公司情况",
        "业务怎么样",
        "什么情况",

        # Medium quality
        "公司的营收增长",
        "分析财务状况",
        "市场表现如何",

        # High quality
        "公司2023年第一季度的营收增长率相比去年同期有何变化？",
        "分析苹果公司2023年Q1的市场份额与主要竞争对手的对比",
        "What are the key risk factors in the company's financial report for 2023?",
    ]

    print("\n" + "=" * 80)
    print("查询优化建议系统演示")
    print("=" * 80)

    for query in scenarios:
        print_analysis(query, service)

    print(f"\n{'=' * 80}")
    print("演示结束")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
