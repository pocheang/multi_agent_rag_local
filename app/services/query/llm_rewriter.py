"""
查询改写服务 - 将口语化问题改写为适合检索的查询。
"""

import json
import logging
import re

from app.services.models.runtime import get_chat_model

logger = logging.getLogger(__name__)

QUERY_REWRITE_PROMPT = """你是一个查询优化专家。将用户的口语化问题改写为更适合文档检索的查询。

用户问题：{{question}}
领域：{{agent_class}}

要求：
1. 提取核心关键词和概念
2. 扩展同义词和相关术语
3. 生成2-3个不同角度的查询变体
4. 保持查询简洁，每个不超过20个字

示例：
用户问题："给我介绍一下有哪些知识"
改写查询：
- 知识库内容概览
- 文档分类和主题
- 可用的知识资源

用户问题："什么是SQL注入攻击？"
改写查询：
- SQL注入漏洞原理
- SQL注入攻击方式
- 数据库注入安全

请严格按照JSON格式输出，不要输出其他内容：
["改写查询1", "改写查询2", "改写查询3"]"""


def rewrite_query_for_retrieval(question: str, agent_class: str = "general") -> list[str]:
    """
    将口语化问题改写为适合检索的查询。

    Args:
        question: 用户原始问题
        agent_class: Agent类别，用于领域相关的改写

    Returns:
        list[str]: [原始问题, 改写版本1, 改写版本2, ...]
    """
    try:
        model = get_chat_model(temperature=0.3)  # 稍高温度增加多样性

        # 构建prompt
        prompt = QUERY_REWRITE_PROMPT.replace("{{question}}", question).replace("{{agent_class}}", agent_class)

        response = model.invoke([("system", prompt)])
        content = response.content.strip()

        # 提取JSON数组
        json_match = re.search(r"\[.*?\]", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            # 清理中文引号
            json_str = json_str.replace('"', '"').replace('"', '"')

            try:
                rewritten_queries = json.loads(json_str)
                if isinstance(rewritten_queries, list) and len(rewritten_queries) > 0:
                    # 过滤空字符串和过长的查询
                    valid_queries = [
                        q.strip() for q in rewritten_queries if q and len(q.strip()) > 0 and len(q.strip()) < 100
                    ]

                    # 返回原始问题 + 改写版本
                    result = [question] + valid_queries[:3]  # 最多3个改写版本
                    logger.info(f"Query rewrite: {question} -> {valid_queries}")
                    return result
                else:
                    logger.warning(f"Invalid rewritten queries format: {rewritten_queries}")
                    return [question]
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error in query rewrite: {e}, content: {json_str}")
                return [question]
        else:
            logger.warning(f"Failed to extract JSON from query rewrite response: {content}")
            return [question]

    except Exception as e:
        logger.error(f"Query rewrite failed: {e}", exc_info=True)
        return [question]


def expand_query_with_synonyms(question: str, agent_class: str = "general") -> list[str]:
    """
    使用同义词和相关术语扩展查询。

    Args:
        question: 用户问题
        agent_class: Agent类别

    Returns:
        list[str]: 扩展后的查询列表
    """
    # 领域相关的同义词映射
    synonyms_map = {
        "cybersecurity": {
            "攻击": ["入侵", "威胁", "exploit"],
            "防护": ["防御", "安全", "protection"],
            "漏洞": ["脆弱性", "vulnerability", "安全缺陷"],
            "安全": ["security", "防护", "保护"],
        },
        "artificial_intelligence": {
            "AI": ["人工智能", "机器学习", "深度学习"],
            "模型": ["model", "网络", "算法"],
            "训练": ["training", "学习", "优化"],
            "神经网络": ["neural network", "深度网络", "DNN"],
        },
        "general": {
            "介绍": ["说明", "解释", "概述"],
            "知识": ["信息", "内容", "资料"],
        },
    }

    expanded = [question]

    # 获取领域相关的同义词
    domain_synonyms = synonyms_map.get(agent_class, {})

    # 简单的同义词替换
    for keyword, synonyms in domain_synonyms.items():
        if keyword in question:
            for synonym in synonyms[:2]:  # 最多2个同义词
                expanded_query = question.replace(keyword, synonym)
                if expanded_query not in expanded:
                    expanded.append(expanded_query)

    return expanded[:4]  # 最多返回4个查询
