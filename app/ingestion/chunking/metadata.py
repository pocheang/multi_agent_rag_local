"""Canonical chunk metadata classification and enrichment."""

from __future__ import annotations

import re
from typing import Any

from .classification import ChunkType, classify_chunk_type

# One definition of what a URL looks like. There were two: a substring test
# for the two scheme literals here, and this pattern in extract_entities, so a
# chunk could report has_url=False and still yield a URL. Case-insensitive
# because both spellings occur in real documents and neither form caught it.
_URL = re.compile(r"https?://\S+", re.IGNORECASE)

# ============================================================================
# 元数据增强
# ============================================================================


def enhance_chunk_metadata(
    chunk_text: str,
    base_metadata: dict[str, Any],
    chunk_index: int,
    total_chunks: int,
    prev_chunk_text: str | None = None,
    next_chunk_text: str | None = None,
) -> dict[str, Any]:
    """
    Enhance chunk metadata with classification and context information

    Args:
        chunk_text: chunk text
        base_metadata: base metadata
        chunk_index: chunk index
        total_chunks: total chunks
        prev_chunk_text: previous chunk text (optional)
        next_chunk_text: next chunk text (optional)

    Returns:
        Enhanced metadata
    """
    metadata = dict(base_metadata)

    # Chunk基本信息
    metadata["chunk_index"] = chunk_index
    metadata["total_chunks"] = total_chunks
    metadata["chunk_length"] = len(chunk_text)
    metadata["word_count"] = len(chunk_text.split())

    # Chunk类型分类
    chunk_type = classify_chunk_type(chunk_text, metadata)
    metadata["chunk_type"] = chunk_type

    # 提取关键信息
    keywords = extract_keywords(chunk_text)
    if keywords:
        metadata["keywords"] = keywords[:10]  # 最多10个关键词

    # 实体识别（简化版）
    entities = extract_entities(chunk_text)
    if entities:
        metadata["entities"] = entities

    # 语义特征
    metadata["has_question"] = "?" in chunk_text or "？" in chunk_text
    metadata["has_code"] = any(marker in chunk_text for marker in ["```", "def ", "class ", "function"])
    metadata["has_url"] = bool(_URL.search(chunk_text))
    metadata["has_email"] = "@" in chunk_text and "." in chunk_text

    # 上下文信息
    if prev_chunk_text:
        metadata["prev_chunk_preview"] = (
            prev_chunk_text[:100] + "..." if len(prev_chunk_text) > 100 else prev_chunk_text
        )

    if next_chunk_text:
        metadata["next_chunk_preview"] = (
            next_chunk_text[:100] + "..." if len(next_chunk_text) > 100 else next_chunk_text
        )

    # 位置信息
    if chunk_index == 0:
        metadata["position"] = "start"
    elif chunk_index == total_chunks - 1:
        metadata["position"] = "end"
    else:
        metadata["position"] = "middle"

    # 重要性评分（简单启发式）
    metadata["importance_score"] = calculate_importance_score(chunk_text, chunk_type, metadata)

    return metadata


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """
    Extract keywords (simplified version based on word frequency and length)

    Args:
        text: Text content
        top_n: Return top N keywords

    Returns:
        List of keywords
    """
    # 移除标点和特殊字符
    clean_text = re.sub(r"[^\w\s]", " ", text.lower())
    words = clean_text.split()

    # 停用词（简化版）
    stopwords = set(
        [
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "是",
            "的",
            "了",
            "在",
            "有",
            "和",
            "与",
            "及",
            "等",
            "中",
            "将",
            "可以",
            "进行",
        ]
    )

    # 过滤停用词和短词
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]

    # 词频统计
    word_freq: dict[str, int] = {}
    for word in keywords:
        word_freq[word] = word_freq.get(word, 0) + 1

    # 按频率排序
    sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, freq in sorted_keywords[:top_n]]


def _first_distinct(values: list[str], limit: int | None = None) -> list[str]:
    """Distinct values in order of first appearance.

    Every one of these was `list(set(values))`, and set iteration order over
    strings depends on `PYTHONHASHSEED`, which Python randomises per process. For
    `acronyms`, `numbers` and `urls` that is not cosmetic: all three are truncated,
    so *which* five acronyms reached a chunk's metadata changed between ingests of
    the same unchanged document. Order of appearance also makes the truncation
    mean something -- "the first five in this chunk" rather than "an arbitrary
    five".

    Found on 2026-09-06 while characterising `split_documents_enhanced` for a
    refactor: two runs of the unmodified splitter produced different metadata.
    """
    distinct = list(dict.fromkeys(values))
    return distinct if limit is None else distinct[:limit]


def extract_entities(text: str) -> dict[str, list[str]]:
    """
    Simplified entity recognition (rule-based)

    Args:
        text: Text content

    Returns:
        Entity dictionary {type: [entity list]}
    """
    entities: dict[str, list[str]] = {}

    # 技术术语（大写缩写）
    acronyms = re.findall(r"\b[A-Z]{2,10}\b", text)
    if acronyms:
        entities["acronyms"] = _first_distinct(acronyms, 5)

    # 数字（版本号、ID等）
    numbers = re.findall(r"\b\d+(?:\.\d+)*\b", text)
    if numbers:
        entities["numbers"] = _first_distinct(numbers, 5)

    # IP地址
    ips = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)
    if ips:
        entities["ip_addresses"] = _first_distinct(ips)

    # 邮箱
    emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
    if emails:
        entities["emails"] = _first_distinct(emails)

    # URL
    urls = _URL.findall(text)
    if urls:
        entities["urls"] = _first_distinct(urls, 3)

    return entities


def calculate_importance_score(text: str, chunk_type: ChunkType, metadata: dict[str, Any]) -> float:
    """
    Calculate chunk importance score (0.0-1.0)

    Args:
        text: Chunk text
        chunk_type: Chunk type
        metadata: Metadata

    Returns:
        Importance score
    """
    score = 0.5  # 基础分数

    # 类型加权
    type_weights = {
        "heading": 0.9,
        "definition": 0.8,
        "procedure": 0.8,
        "table": 0.7,
        "code": 0.6,
        "list": 0.6,
        "quote": 0.5,
        "paragraph": 0.5,
        "metadata": 0.3,
        "mixed": 0.5,
    }
    score = type_weights.get(chunk_type, 0.5)

    # 位置加权（开头和结尾更重要）
    if metadata.get("position") == "start":
        score += 0.1
    elif metadata.get("position") == "end":
        score += 0.05

    # 长度调整（太短或太长都降低分数）
    chunk_length = len(text)
    if chunk_length < 50:
        score -= 0.1
    elif chunk_length > 2000:
        score -= 0.05
    elif 200 <= chunk_length <= 800:
        score += 0.05  # 理想长度

    # 包含关键元素加分
    if metadata.get("has_code"):
        score += 0.05
    if metadata.get("keywords") and len(metadata["keywords"]) >= 3:
        score += 0.05
    if metadata.get("entities"):
        score += 0.05

    # 限制在0-1范围
    return max(0.0, min(1.0, score))
