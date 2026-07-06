"""
Agent Usage Examples - Complete demonstrations of multi-agent RAG system.

This module provides practical examples for using different agents.
"""

import asyncio
import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Simple Vector RAG Query
# ============================================================================

def example_vector_rag_basic():
    """
    Example: Basic vector RAG query for simple fact retrieval.

    Use case: Query documents for specific information.
    """
    from app.agents.vector_rag_agent import run_vector_rag

    print("\n" + "="*80)
    print("Example 1: Basic Vector RAG Query")
    print("="*80)

    question = "什么是Docker容器技术？"

    print(f"\n问题: {question}")
    print("\n执行中...")

    result = run_vector_rag(
        question=question,
        retrieval_strategy="hybrid"  # 使用混合检索策略
    )

    print(f"\n检索结果:")
    print(f"- 检索到的文档块数: {result['retrieved_count']}")
    print(f"- 有效命中数: {result['effective_hit_count']}")
    print(f"- 引用数量: {len(result['citations'])}")

    if result['citations']:
        print(f"\n引用来源:")
        for i, citation in enumerate(result['citations'][:3], 1):
            print(f"  {i}. {citation['source']}")

    print(f"\n上下文预览:")
    context_preview = result['context'][:200] + "..." if len(result['context']) > 200 else result['context']
    print(f"  {context_preview}")


# ============================================================================
# Example 2: Graph RAG for Relationship Query
# ============================================================================

def example_graph_rag_relationships():
    """
    Example: Graph RAG for entity relationship queries.

    Use case: Query relationships between entities in knowledge graph.
    """
    from app.agents.graph_rag_agent import run_graph_rag

    print("\n" + "="*80)
    print("Example 2: Graph RAG - Entity Relationships")
    print("="*80)

    question = "Kubernetes和Docker之间有什么关系？"

    print(f"\n问题: {question}")
    print("\n执行中...")

    result = run_graph_rag(question=question)

    print(f"\n图谱查询结果:")
    print(f"- 实体数量: {len(result['entities'])}")
    print(f"- 关系数量: {len(result['neighbors'])}")
    print(f"- 路径数量: {len(result['paths'])}")
    print(f"- 图谱信号分数: {result['graph_signal_score']:.2f}")

    if result['entities']:
        print(f"\n识别的实体:")
        for entity in result['entities'][:5]:
            print(f"  - {entity}")

    if result['neighbors']:
        print(f"\n邻居关系:")
        for neighbor in result['neighbors'][:3]:
            print(f"  - {neighbor}")

    if result.get('fallback_used'):
        print(f"\n⚠️ 注意: 图谱查询失败，已fallback到向量检索")


# ============================================================================
# Example 3: Complete Workflow Query
# ============================================================================

def example_complete_workflow():
    """
    Example: Complete workflow with automatic routing.

    Use case: Let the system automatically choose the best agent.
    """
    from app.graph.workflow import run_query

    print("\n" + "="*80)
    print("Example 3: Complete Workflow with Auto Routing")
    print("="*80)

    question = "比较REST API和GraphQL的优缺点"

    print(f"\n问题: {question}")
    print("\n执行中...")

    result = run_query(
        question=question,
        use_reasoning=True,  # 使用推理模型提高质量
        use_web_fallback=False,
        memory_context="",
    )

    print(f"\n查询结果:")
    print(f"- 路由: {result['route']}")
    print(f"- 技能: {result.get('skill', 'N/A')}")
    print(f"- Agent类别: {result.get('agent_class', 'N/A')}")
    print(f"- 检测语言: {result.get('detected_language', 'N/A')}")

    print(f"\n答案:")
    answer = result.get('answer', '')
    answer_preview = answer[:300] + "..." if len(answer) > 300 else answer
    print(f"  {answer_preview}")

    # 显示使用的数据源
    vector_result = result.get('vector_result', {})
    graph_result = result.get('graph_result', {})
    web_result = result.get('web_result', {})

    print(f"\n数据源:")
    print(f"- Vector检索: {vector_result.get('retrieved_count', 0)} chunks")
    print(f"- Graph实体: {len(graph_result.get('entities', []))}")
    print(f"- Web搜索: {'是' if web_result.get('used') else '否'}")


# ============================================================================
# Example 4: ReAct Agent for Complex Reasoning
# ============================================================================

def example_react_agent():
    """
    Example: ReAct agent for multi-step reasoning.

    Use case: Complex queries requiring iterative information gathering.
    """
    from app.agents.react_agent import run_react_agent

    print("\n" + "="*80)
    print("Example 4: ReAct Agent - Multi-Step Reasoning")
    print("="*80)

    question = "分析微服务架构的优势，然后推荐适合的技术栈"

    print(f"\n问题: {question}")
    print("\n执行中（可能需要几秒）...")

    result = run_react_agent(
        question=question,
        use_reasoning=False,
        max_iterations=5
    )

    print(f"\n推理过程:")
    print(f"- 使用迭代数: {result['iterations_used']}/{5}")

    # 显示推理历史
    if result.get('react_history'):
        print(f"\n推理步骤:")
        for i, step in enumerate(result['react_history'], 1):
            thought = step.get('thought', {})
            observation = step.get('observation', {})
            print(f"\n  第{i}轮:")
            print(f"    思考: {thought.get('thought', 'N/A')[:100]}...")
            print(f"    行动: {thought.get('action', 'N/A')}")
            if observation:
                print(f"    观察: {observation.get('result', 'N/A')[:100]}...")

    print(f"\n最终答案:")
    answer = result.get('answer', '')
    answer_preview = answer[:300] + "..." if len(answer) > 300 else answer
    print(f"  {answer_preview}")


# ============================================================================
# Example 5: Enhanced RAG with Quality Assurance
# ============================================================================

async def example_enhanced_rag_workflow():
    """
    Example: Enhanced RAG workflow with quality assurance.

    Use case: Critical queries requiring high quality guarantees.
    """
    from app.agents.enhanced_rag_workflow import EnhancedRAGWorkflow

    print("\n" + "="*80)
    print("Example 5: Enhanced RAG with Quality Assurance")
    print("="*80)

    question = "详细解释零信任安全架构的核心原则"

    print(f"\n问题: {question}")
    print("\n执行中（包含质量检查）...")

    workflow = EnhancedRAGWorkflow(
        max_route_retries=1,
        max_answer_retries=1,
        enable_context_tracking=True
    )

    result = await workflow.execute_query(
        query=question,
        user_id="demo_user",
        session_id="demo_session"
    )

    print(f"\n查询结果:")
    print(f"- 路由: {result['route_used']}")
    print(f"- 技能: {result['skill_used']}")

    # 质量报告
    quality = result['quality_report']
    print(f"\n质量报告:")
    print(f"- 质量等级: {quality.quality_level}")
    print(f"- 综合分数: {quality.overall_score:.2f}")
    print(f"- 路由置信度: {quality.route_confidence:.2f}")
    print(f"- 检索质量: {quality.retrieval_quality:.2f}")
    print(f"- 答案质量: {quality.answer_quality:.2f}")

    print(f"\n答案:")
    answer = result['answer']
    answer_preview = answer[:300] + "..." if len(answer) > 300 else answer
    print(f"  {answer_preview}")

    # 执行元数据
    metadata = result['execution_metadata']
    print(f"\n性能指标:")
    print(f"- 总耗时: {metadata['total_time_ms']:.0f}ms")
    print(f"- 路由重试: {metadata.get('route_retries', 0)}")
    print(f"- 答案重试: {metadata.get('answer_retries', 0)}")


# ============================================================================
# Example 6: Custom Agent Configuration
# ============================================================================

def example_custom_agent_configuration():
    """
    Example: Customizing agent behavior with specific parameters.

    Use case: Fine-tuning agent behavior for specific requirements.
    """
    from app.agents.vector_rag_agent import run_vector_rag
    from app.agents.router_agent import decide_route

    print("\n" + "="*80)
    print("Example 6: Custom Agent Configuration")
    print("="*80)

    question = "网络安全威胁防护措施"

    # 1. 强制指定agent类别
    print(f"\n1. 使用agent_class_hint指定agent类别:")
    decision = decide_route(
        question,
        agent_class_hint="cybersecurity"  # 强制使用网络安全agent
    )
    print(f"   - 路由: {decision.route}")
    print(f"   - Agent类别: {decision.agent_class}")
    print(f"   - 技能: {decision.skill}")

    # 2. 指定文档源
    print(f"\n2. 限制文档源范围:")
    result = run_vector_rag(
        question=question,
        allowed_sources=["security_guide.pdf", "threat_report.pdf"],
        retrieval_strategy="rerank"  # 使用rerank策略获得最佳结果
    )
    print(f"   - 检索到: {result['retrieved_count']} 个结果")
    print(f"   - 文档源: {set(c['source'] for c in result['citations'])}")

    # 3. 使用不同的检索策略
    print(f"\n3. 对比不同检索策略:")
    strategies = ["hybrid", "dense", "bm25"]
    for strategy in strategies:
        result = run_vector_rag(
            question=question,
            retrieval_strategy=strategy
        )
        print(f"   - {strategy}: {result['effective_hit_count']} 有效命中")


# ============================================================================
# Example 7: Router Decision Analysis
# ============================================================================

def example_router_analysis():
    """
    Example: Analyzing router decisions for different query types.

    Use case: Understanding how queries are classified and routed.
    """
    from app.agents.router_agent import decide_route

    print("\n" + "="*80)
    print("Example 7: Router Decision Analysis")
    print("="*80)

    test_queries = [
        "什么是Kubernetes？",
        "Docker和Kubernetes的关系",
        "比较REST和gRPC的性能",
        "分析系统架构，然后推荐优化方案",
        "2024年最新的AI发展趋势",
    ]

    print(f"\n分析 {len(test_queries)} 个不同类型的查询:\n")

    for i, query in enumerate(test_queries, 1):
        decision = decide_route(query)

        print(f"{i}. 查询: {query}")
        print(f"   → 路由: {decision.route}")
        print(f"   → 技能: {decision.skill}")
        print(f"   → Agent类别: {decision.agent_class}")
        print(f"   → 置信度: {decision.confidence:.2f}")
        print(f"   → 原因: {decision.reason}")
        print()


# ============================================================================
# Example 8: Agent Health Check
# ============================================================================

def example_agent_health_check():
    """
    Example: Checking agent health and validation.

    Use case: System diagnostics and health monitoring.
    """
    from app.agents.agent_validator import validate_agent_integration

    print("\n" + "="*80)
    print("Example 8: Agent Health Check")
    print("="*80)

    print("\n执行健康检查...")

    results = validate_agent_integration()

    print(f"\n整体状态: {results['overall_status']}")
    print(f"\n统计:")
    summary = results['summary']
    print(f"  - 总计: {summary['total']}")
    print(f"  - 正常: {summary['ok']}")
    print(f"  - Fallback: {summary['fallback']}")
    print(f"  - 错误: {summary['error']}")

    print(f"\n详细结果:")
    for agent_name, detail in results['details'].items():
        status = detail.get('status', 'unknown')
        status_icon = "✓" if status == "ok" else "⚠" if status == "fallback" else "✗"
        print(f"  {status_icon} {agent_name}: {status}")
        if status == "error":
            print(f"     错误: {detail.get('error', 'N/A')}")


# ============================================================================
# Main Demo Runner
# ============================================================================

def run_all_examples():
    """Run all examples sequentially."""
    print("\n" + "="*80)
    print("Multi-Agent RAG System - Usage Examples")
    print("="*80)

    try:
        # Example 1: Vector RAG
        example_vector_rag_basic()

        # Example 2: Graph RAG
        example_graph_rag_relationships()

        # Example 3: Complete Workflow
        example_complete_workflow()

        # Example 4: ReAct Agent
        example_react_agent()

        # Example 5: Enhanced RAG (async)
        print("\n运行异步示例...")
        asyncio.run(example_enhanced_rag_workflow())

        # Example 6: Custom Configuration
        example_custom_agent_configuration()

        # Example 7: Router Analysis
        example_router_analysis()

        # Example 8: Health Check
        example_agent_health_check()

        print("\n" + "="*80)
        print("所有示例执行完成!")
        print("="*80)

    except Exception as e:
        logger.exception(f"示例执行失败: {e}")
        print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    # 运行所有示例
    run_all_examples()

    # 或运行单个示例:
    # example_vector_rag_basic()
    # example_graph_rag_relationships()
    # example_complete_workflow()
    # example_react_agent()
    # asyncio.run(example_enhanced_rag_workflow())
    # example_custom_agent_configuration()
    # example_router_analysis()
    # example_agent_health_check()
