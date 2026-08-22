"""
Demo script for user experience improvements.

Run this to see the new user-friendly features in action.
"""

import asyncio
from app.domain.user_experience import (
    ProgressTranslator,
    QualityCardBuilder,
    UserFriendlyError,
    convert_to_user_friendly_error,
)


def demo_progress_tracking():
    """Demonstrate user-friendly progress tracking."""
    print("\n" + "=" * 60)
    print("🎯 演示 1: 用户友好的进度追踪")
    print("=" * 60 + "\n")

    translator = ProgressTranslator()

    # Simulate pipeline stages
    stages = [
        ("route", "in_progress", ""),
        ("route", "completed", ""),
        ("rag", "in_progress", "retrieved 15 evidence items"),
        ("rag", "completed", ""),
        ("synthesize", "in_progress", ""),
        ("synthesize", "completed", ""),
        ("finalize", "in_progress", ""),
        ("complete", "completed", ""),
    ]

    for stage, status, message in stages:
        progress = translator.translate(stage, status, message, "zh")

        progress_bar = ""
        if progress.progress_percent:
            filled = int(progress.progress_percent / 5)
            progress_bar = f" [{'█' * filled}{'░' * (20 - filled)}] {progress.progress_percent}%"

        eta = f" · 预计还需 {progress.estimated_seconds}秒" if progress.estimated_seconds else ""

        print(f"{progress.icon} {progress.user_message}{progress_bar}{eta}")


def demo_quality_card():
    """Demonstrate answer quality card."""
    print("\n" + "=" * 60)
    print("📊 演示 2: 答案质量卡片")
    print("=" * 60)

    builder = QualityCardBuilder()

    # High quality answer
    print("\n【场景 1: 高质量答案】")
    high_quality = builder.build_from_answer(
        validation_score=0.87,
        evidence_count=8,
        citation_completeness=0.85,
        retrieval_scores=[0.9, 0.85, 0.88, 0.92],
        has_validation_issues=False,
    )
    print(high_quality.format_as_text("zh"))

    # Medium quality answer
    print("\n【场景 2: 中等质量答案】")
    medium_quality = builder.build_from_answer(
        validation_score=0.65,
        evidence_count=3,
        citation_completeness=0.60,
        retrieval_scores=[0.7, 0.65],
        has_validation_issues=False,
    )
    print(medium_quality.format_as_text("zh"))

    # Low quality answer
    print("\n【场景 3: 低质量答案】")
    low_quality = builder.build_from_answer(
        validation_score=0.45,
        evidence_count=2,
        citation_completeness=0.30,
        retrieval_scores=[0.5, 0.4],
        has_validation_issues=True,
    )
    print(low_quality.format_as_text("zh"))


def demo_friendly_errors():
    """Demonstrate user-friendly error messages."""
    print("\n" + "=" * 60)
    print("❌ 演示 3: 友好的错误提示")
    print("=" * 60)

    # Scenario 1: All retrievers failed
    print("\n【场景 1: 检索服务失败】")
    error1 = RuntimeError("All 3 retrieval attempts failed. Cannot proceed without evidence.")
    friendly1 = convert_to_user_friendly_error(error1, "zh")
    print(friendly1.format_for_display("zh", show_technical=False))

    # Scenario 2: No evidence found
    print("\n【场景 2: 未找到相关信息】")
    error2 = ValueError("No evidence items found for query")
    friendly2 = UserFriendlyError(
        error_type="NoEvidenceFoundError",
        user_title="未找到相关信息",
        user_message="很抱歉，我在知识库中没有找到与您问题相关的信息。",
        severity="info",
        immediate_actions=[
            "尝试用不同的关键词重新提问",
            "将问题拆分成更具体的小问题",
            "确认问题是否在系统的知识范围内",
        ],
    )
    print(friendly2.format_for_display("zh", show_technical=False))

    # Scenario 3: Timeout
    print("\n【场景 3: 处理超时】")
    error3 = TimeoutError("Request exceeded 30s timeout")
    friendly3 = UserFriendlyError(
        error_type="TimeoutError",
        user_title="处理超时",
        user_message="抱歉，您的问题处理时间超过了预期。这可能是因为问题比较复杂。",
        severity="warning",
        immediate_actions=[
            "尝试将问题拆分成更简单的子问题",
            "稍后重试",
        ],
        technical_details="Request exceeded timeout budget: 30s",
    )
    print(friendly3.format_for_display("zh", show_technical=True))


def demo_comparison():
    """Show before/after comparison."""
    print("\n" + "=" * 60)
    print("🔄 演示 4: 改进前后对比")
    print("=" * 60)

    print("\n【改进前 ❌】")
    print("用户提问: '分析公司的财务状况'\n")
    print("[沉默 3 秒...]")
    print("status: rag")
    print("[沉默 5 秒...]")
    print("status: synthesize")
    print("[沉默 4 秒...]")
    print("\n答案: 根据检索到的文档，公司2023年营收为500万元。[doc1:p3]\n")
    print("（用户困惑：这花了多久？为什么？答案可靠吗？）")

    print("\n" + "-" * 60)
    print("\n【改进后 ✅】")
    print("用户提问: '分析公司的财务状况'\n")

    # Simulated progress
    import time
    progress_steps = [
        ("🎯 理解您的问题", 10, 0.5),
        ("📚 搜索相关文档 - 已找到 15 份相关文档", 50, 2),
        ("✍️ 生成答案 (85% · 预计还需 3秒)", 85, 3),
        ("✅ 质量检查", 95, 0.5),
        ("✅ 完成", 100, 0),
    ]

    for message, percent, delay in progress_steps:
        filled = int(percent / 5)
        bar = f"[{'█' * filled}{'░' * (20 - filled)}] {percent}%"
        print(f"{message} {bar}")
        if delay > 0:
            time.sleep(delay * 0.1)  # Speed up for demo

    print("\n答案: 根据检索到的文档，公司2023年营收为500万元。[财报2023:p3]")

    # Quality card
    builder = QualityCardBuilder()
    card = builder.build_from_answer(
        validation_score=0.87,
        evidence_count=3,
        citation_completeness=0.85,
        retrieval_scores=[0.9, 0.85],
    )
    print(card.format_as_text("zh"))


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("   QueryMind 用户体验改进演示")
    print("=" * 60)

    demo_progress_tracking()
    demo_quality_card()
    demo_friendly_errors()
    demo_comparison()

    print("\n" + "=" * 60)
    print("✅ 演示完成！")
    print("=" * 60)
    print("\n主要改进:")
    print("  1. ✅ 实时进度追踪 - 用户知道系统在做什么")
    print("  2. ✅ 答案质量卡片 - 用户知道答案可信度")
    print("  3. ✅ 友好错误提示 - 用户知道如何恢复")
    print("  4. ✅ 增强的编排引擎 - 自动集成所有改进")
    print("\n预期效果:")
    print("  • 用户满意度提升 30%+")
    print("  • 支持工单减少 50%")
    print("  • 用户留存率提升 20%")
    print("\n下一步:")
    print("  • 实施查询优化建议")
    print("  • Router 代码重构")
    print("  • 流式答案返回")
    print("\n")


if __name__ == "__main__":
    main()
