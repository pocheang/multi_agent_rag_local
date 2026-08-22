"""
Enhanced Graph Tools configuration and utilities.

This module provides centralized configuration for graph_tools_enhanced.py
including entity aliases, relation weights, and optimization parameters.
"""

from typing import Final

# ============================================================================
# Entity Normalization and Aliases
# ============================================================================

# Comprehensive entity aliases for better cross-language matching
ENTITY_ALIASES: Final[dict[str, str]] = {
    # AI/ML terms
    "ai": "artificial intelligence",
    "a.i.": "artificial intelligence",
    "llm": "large language model",
    "大模型": "large language model",
    "大语言模型": "large language model",
    "ml": "machine learning",
    "机器学习": "machine learning",
    "dl": "deep learning",
    "深度学习": "deep learning",
    "nlp": "natural language processing",
    "自然语言处理": "natural language processing",
    # RAG specific
    "rag": "retrieval augmented generation",
    "检索增强生成": "retrieval augmented generation",
    "向量检索": "vector retrieval",
    "vector search": "vector retrieval",
    "向量搜索": "vector retrieval",
    # Security
    "网络安全": "cybersecurity",
    "资安": "cybersecurity",
    "信息安全": "information security",
    "infosec": "information security",
    "资讯安全": "information security",
    # Database
    "数据库": "database",
    "db": "database",
    "图数据库": "graph database",
    "neo4j": "graph database",
    "关系数据库": "relational database",
    "nosql": "nosql database",
    # Common tech
    "api": "application programming interface",
    "rest": "representational state transfer",
    "restful": "representational state transfer",
    "gpu": "graphics processing unit",
    "cpu": "central processing unit",
    "显卡": "graphics processing unit",
    "处理器": "central processing unit",
    # Cloud & DevOps
    "k8s": "kubernetes",
    "docker": "container",
    "容器": "container",
    "微服务": "microservices",
    "云计算": "cloud computing",
}

# ============================================================================
# Relation Classification
# ============================================================================

# Noisy relations to filter out
NOISY_RELATIONS: Final[frozenset[str]] = frozenset(
    {
        "related",
        "关联",
        "相关",
        "link",
        "links",
        "linked_to",
        "unknown",
        "其他",
        "other",
        "misc",
        "general",
        "通用",
        "associated",
        "connected",
    }
)

# High-value relations (semantic meaning, weighted higher)
HIGH_VALUE_RELATIONS: Final[frozenset[str]] = frozenset(
    {
        # Causality
        "causes",
        "导致",
        "leads_to",
        "引起",
        "results_in",
        "产生",
        # Dependency
        "depends",
        "依赖",
        "requires",
        "需要",
        "relies_on",
        "基于",
        # Usage
        "uses",
        "利用",
        "employs",
        "采用",
        "applies",
        "应用",
        # Impact
        "targets",
        "攻击",
        "affects",
        "影响",
        "impacts",
        "作用于",
        # Mitigation
        "mitigates",
        "缓解",
        "prevents",
        "防止",
        "protects",
        "保护",
        # Implementation
        "implements",
        "实现",
        "contains",
        "包含",
        "provides",
        "提供",
        # Transformation
        "produces",
        "generates",
        "生成",
        "creates",
        "创建",
        # Enhancement
        "improves",
        "改进",
        "enhances",
        "增强",
        "optimizes",
        "优化",
    }
)

# ============================================================================
# Scoring and Ranking Parameters
# ============================================================================

# Base weights for different relation types
RELATION_WEIGHT_HIGH: Final[float] = 1.0
RELATION_WEIGHT_MEDIUM: Final[float] = 0.6
RELATION_WEIGHT_LOW: Final[float] = 0.3

# Context quality boost parameters
QUALITY_BOOST_MAX: Final[float] = 0.3  # Up to 30% boost for high quality
QUALITY_BOOST_THRESHOLD: Final[float] = 0.7  # Quality threshold for bonus

# Entity retrieval multipliers (retrieve more, then rank)
ENTITY_RETRIEVAL_MULTIPLIER: Final[int] = 2
NEIGHBOR_RETRIEVAL_MULTIPLIER: Final[int] = 2
PATH_RETRIEVAL_MULTIPLIER: Final[int] = 2

# Multi-hop path scoring
PATH_WEIGHT_BOOST: Final[float] = 1.2  # 20% boost for valuable paths
NEIGHBOR_QUALITY_BOOST: Final[float] = 1.15  # 15% boost for high-quality neighbors

# Graph signal score component weights
SIGNAL_WEIGHT_ENTITY: Final[float] = 0.35
SIGNAL_WEIGHT_NEIGHBOR: Final[float] = 0.40
SIGNAL_WEIGHT_PATH: Final[float] = 0.25

# Confidence thresholds
CONFIDENCE_HIGH_SIGNAL: Final[float] = 0.7
CONFIDENCE_HIGH_ENTITIES: Final[int] = 3
CONFIDENCE_HIGH_NEIGHBORS: Final[int] = 5
CONFIDENCE_HIGH_PATHS: Final[int] = 3

CONFIDENCE_MEDIUM_SIGNAL: Final[float] = 0.5
CONFIDENCE_MEDIUM_ENTITIES: Final[int] = 2
CONFIDENCE_MEDIUM_NEIGHBORS: Final[int] = 3

# Entity scoring
ENTITY_COUNT_OPTIMAL: Final[int] = 5  # Optimal entity count for full score

# ============================================================================
# Token Pattern (kept from original for compatibility)
# ============================================================================

TOKEN_PATTERN_STRING: Final[str] = (
    r"[A-Za-z0-9_\-]{2,}|"  # English words/acronyms (min 2 chars)
    r"[一-鿿]{2,}|"  # Chinese (min 2 chars)
    r"[A-Z]{2,}"  # Acronyms in caps
)
