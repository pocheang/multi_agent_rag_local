"""
多查询检索服务 - 对多个查询分别检索并合并结果。
"""

import logging
from collections import defaultdict

from app.retrievers.hybrid.retriever import hybrid_search_with_diagnostics
from app.services.query.llm_rewriter import rewrite_query_for_retrieval

logger = logging.getLogger(__name__)


def multi_query_retrieval(
    question: str,
    agent_class: str = "general",
    allowed_sources: list[str] | None = None,
    top_k: int = 5,
    enable_rewrite: bool = True,
) -> tuple[list[dict], dict]:
    """
    多查询检索：对原始问题和改写版本分别检索，合并结果。

    Args:
        question: 用户原始问题
        agent_class: Agent类别
        allowed_sources: 允许的文档来源
        top_k: 每个查询返回的结果数
        enable_rewrite: 是否启用查询改写

    Returns:
        tuple[list[dict], dict]: (合并后的结果, 诊断信息)
    """
    # 生成查询变体
    if enable_rewrite:
        queries = rewrite_query_for_retrieval(question, agent_class)
        logger.info(f"Multi-query retrieval with {len(queries)} queries: {queries}")
    else:
        queries = [question]

    # 对每个查询分别检索
    all_results = []
    query_diagnostics = {}

    for i, query in enumerate(queries):
        try:
            results, diagnostics = hybrid_search_with_diagnostics(
                query,
                allowed_sources=allowed_sources,
            )

            # 记录每个查询的结果数
            query_diagnostics[f"query_{i + 1}"] = {
                "query": query,
                "results_count": len(results),
                "diagnostics": diagnostics,
            }

            # 为每个结果添加来源查询信息
            for result in results:
                result["source_query"] = query
                result["query_index"] = i

            all_results.extend(results)

        except Exception as e:
            logger.error(f"Query retrieval failed for '{query}': {e}")
            query_diagnostics[f"query_{i + 1}"] = {
                "query": query,
                "error": str(e),
            }

    # 合并和去重
    merged_results = merge_and_deduplicate_results(all_results, top_k)

    # 汇总诊断信息
    merged_diagnostics = {
        "total_queries": len(queries),
        "queries": queries,
        "query_diagnostics": query_diagnostics,
        "merged_results_count": len(merged_results),
        "original_results_count": len(all_results),
    }

    return merged_results, merged_diagnostics


def merge_and_deduplicate_results(results: list[dict], top_k: int) -> list[dict]:
    """
    合并多个查询的结果，去重并重新排序。

    策略：
    1. 按文档ID去重，保留最高分数
    2. 如果同一文档被多个查询检索到，提升其分数（投票机制）
    3. 按最终分数排序

    Args:
        results: 所有查询的结果列表
        top_k: 返回的结果数量

    Returns:
        list[dict]: 去重并排序后的结果
    """
    if not results:
        return []

    # 按文档ID分组
    doc_groups = defaultdict(list)
    for result in results:
        # 使用文档来源作为唯一标识
        doc_id = result.get("metadata", {}).get("source", "") + str(result.get("metadata", {}).get("chunk_index", ""))
        doc_groups[doc_id].append(result)

    # 合并同一文档的多个结果
    merged = []
    for _doc_id, doc_results in doc_groups.items():
        # 选择分数最高的结果作为基础
        best_result = max(doc_results, key=lambda x: x.get("score", 0))

        # 计算投票加成：被多个查询检索到的文档更重要
        vote_count = len(doc_results)
        vote_bonus = (vote_count - 1) * 0.1  # 每多一个查询投票，加0.1分

        # 计算最终分数
        base_score = best_result.get("score", 0)
        final_score = min(base_score + vote_bonus, 1.0)  # 最高1.0

        # 记录投票信息
        best_result["vote_count"] = vote_count
        best_result["vote_bonus"] = vote_bonus
        best_result["final_score"] = final_score
        best_result["original_score"] = base_score

        # 记录所有来源查询
        source_queries = list(set(r.get("source_query", "") for r in doc_results))
        best_result["source_queries"] = source_queries

        merged.append(best_result)

    # 按最终分数排序
    merged.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    # 返回top_k结果
    return merged[:top_k]
