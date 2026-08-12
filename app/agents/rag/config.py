"""
Configuration constants for Graph RAG agents.

This module centralizes all thresholds, patterns, and term lists
to make them easier to maintain and tune.
"""

import re
from typing import Final

# ============================================================================
# Quality Analysis Thresholds
# ============================================================================

# PDF quality score thresholds
QUALITY_THRESHOLD_HIGH: Final[float] = 0.7
QUALITY_THRESHOLD_MEDIUM: Final[float] = 0.5
QUALITY_THRESHOLD_LOW: Final[float] = 0.3

# Quality score component weights
QUALITY_WEIGHT_STRUCTURE: Final[float] = 0.4
QUALITY_WEIGHT_CONTENT: Final[float] = 0.4
QUALITY_WEIGHT_METADATA: Final[float] = 0.2

# Content density thresholds (words per 100 chars)
DENSITY_OPTIMAL_MIN: Final[float] = 3.0
DENSITY_OPTIMAL_MAX: Final[float] = 20.0
DENSITY_ACCEPTABLE_MIN: Final[float] = 2.0
DENSITY_ACCEPTABLE_MAX: Final[float] = 25.0

# Word count thresholds
WORD_COUNT_HIGH: Final[int] = 500
WORD_COUNT_MEDIUM: Final[int] = 200

# Technical term thresholds
TECH_TERM_COUNT_HIGH: Final[int] = 10
TECH_TERM_COUNT_MEDIUM: Final[int] = 5

# Page count thresholds
PAGE_COUNT_HIGH: Final[int] = 10
PAGE_COUNT_MEDIUM: Final[int] = 5

# ============================================================================
# Entity Extraction Configuration
# ============================================================================

# Entity extraction limits
DEFAULT_ENTITY_LIMIT: Final[int] = 20
MIN_ENTITY_LENGTH: Final[int] = 2
MAX_ENTITY_LENGTH: Final[int] = 12
MAX_ENTITY_WORDS: Final[int] = 4

# Document context analysis
DEFAULT_TOP_K_DOCS: Final[int] = 3
MIN_ENTITIES_FOR_HIGH_CONFIDENCE: Final[int] = 5
MIN_ENTITIES_FOR_MEDIUM_CONFIDENCE: Final[int] = 3

# ============================================================================
# Graph Lookup Parameters
# ============================================================================

# Adaptive parameters by quality level
GRAPH_PARAMS_HIGH_QUALITY = {
    "max_entities": 12,
    "max_neighbors": 20,
    "max_paths": 12,
}

GRAPH_PARAMS_MEDIUM_QUALITY = {
    "max_entities": 10,
    "max_neighbors": 15,
    "max_paths": 10,
}

GRAPH_PARAMS_LOW_QUALITY = {
    "max_entities": 8,
    "max_neighbors": 12,
    "max_paths": 8,
}

# Graph signal scoring
GRAPH_SIGNAL_THRESHOLD_HIGH: Final[float] = 0.7
GRAPH_SIGNAL_THRESHOLD_MEDIUM: Final[float] = 0.5
GRAPH_SIGNAL_THRESHOLD_LOW: Final[float] = 0.3

# ============================================================================
# Precompiled Regular Expressions
# ============================================================================

# Structure detection patterns
PATTERN_HEADERS = re.compile(r"^#+\s+.+$|^\d+\.\s+[A-Z][^.]+$", re.MULTILINE)

PATTERN_TABLES = re.compile(r"\|.+\|.+\||\t.+\t.+\t")

PATTERN_LISTS = re.compile(r"^[-*•]\s+.+$|^\d+\.\s+.+$", re.MULTILINE)

PATTERN_REFERENCES = re.compile(r"(?i)(references?|bibliography|citations?|参考文献)")

# Technical phrase patterns
PATTERN_TECHNICAL_PHRASES_EN = re.compile(
    r"\b(?:"
    r"large language models?|"
    r"retrieval[- ]augmented generation|"
    r"natural language processing|"
    r"machine learning|"
    r"deep learning|"
    r"artificial intelligence|"
    r"knowledge graph|"
    r"transformer architecture|"
    r"intelligent customer service systems?"
    r")\b",
    re.IGNORECASE,
)

PATTERN_TECHNICAL_PHRASES_ZH = re.compile(
    r"(?:"
    r"大语言模型|"
    r"自然语言处理|"
    r"检索增强生成|"
    r"智能客服系统|"
    r"机器翻译|"
    r"知识图谱|"
    r"注意力机制|"
    r"文档理解与分析|"
    r"信息检索"
    r")"
)

# Entity extraction patterns
PATTERN_PROPER_NOUNS = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){0,3}\b")

PATTERN_ACRONYMS = re.compile(r"\b[A-Z]{2,6}s?\b")

PATTERN_CAMEL_CASE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]+)+\b")

PATTERN_CHINESE_TERMS = re.compile(r"[一-鿿]{2,10}(?:模型|系统|机制|架构|翻译|分析|处理)")

# Technical terms for content quality
PATTERN_TECH_TERMS = re.compile(
    r"\b(?:AI|ML|API|system|process|data|algorithm|model|method|approach|"
    r"analysis|implementation|framework|architecture|optimization)\b",
    re.IGNORECASE,
)

# Relation query keywords
PATTERN_RELATION_KEYWORDS = re.compile(
    r"\b(?:relationship|关系|connect|连接|relate|关联|between|之间|"
    r"link|链接|impact|影响|cause|导致|depend|依赖)\b",
    re.IGNORECASE,
)

# Potential entities in query
PATTERN_QUERY_ENTITIES = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|[A-Z]{2,5}\b|[一-鿿]{2,}")

# ============================================================================
# Term Lists
# ============================================================================

# English noise terms to filter out
ENGLISH_NOISE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "introduction",
        "overview",
        "description",
        "component",
        "components",
        "question",
        "translation",
        "modern",
        "these",
        "allows",
        "self",
        "references",
        "applications",
        "challenges",
    }
)

# Chinese noise terms
CHINESE_NOISE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "主要特点包括",
        "基本概念",
        "关键技术",
        "应用场景",
        "参考文献",
    }
)

# Chinese noise patterns (partial matches)
CHINESE_NOISE_PATTERNS: Final[tuple[str, ...]] = (
    "是一种",
    "包括",
    "通过",
    "允许",
    "能够",
    "从而",
    "进行",
    "提高",
    "减少",
    "支持",
    "结合",
    "应用于",
)

# Chinese suffix noise
CHINESE_SUFFIX_NOISE: Final[tuple[str, ...]] = (
    "的",
    "了",
    "们",
    "及其",
)

# English single-term keywords (allowed despite being single words)
ENGLISH_SINGLE_TERM_KEYWORDS: Final[tuple[str, ...]] = (
    "model",
    "models",
    "system",
    "systems",
    "framework",
    "retrieval",
    "generation",
    "language",
    "processing",
    "learning",
    "attention",
    "graph",
    "transformer",
    "chatgpt",
    "claude",
    "copilot",
    "docker",
    "kubernetes",
    "redis",
    "mongodb",
    "postgresql",
    "mysql",
    "neo4j",
)

# Chinese term keywords (must contain these to be valid)
CHINESE_TERM_KEYWORDS: Final[tuple[str, ...]] = (
    "模型",
    "系统",
    "架构",
    "机制",
    "生成",
    "检索",
    "学习",
    "语言",
    "处理",
    "文档",
    "分析",
    "翻译",
    "数据库",
    "安全",
    "智能",
    "客服",
    "知识图谱",
)
