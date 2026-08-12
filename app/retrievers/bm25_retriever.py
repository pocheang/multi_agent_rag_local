import re
from functools import lru_cache

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - optional dependency fallback
    BM25Okapi = None  # type: ignore[assignment]

from app.retrievers.stores.corpus import read_corpus_records

# English tokenization pattern (original)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """
    Basic tokenization for English and Chinese text.

    English: splits on whitespace and punctuation
    Chinese: treats each character as a token (suboptimal for BM25)
    """
    return TOKEN_PATTERN.findall((text or "").lower())


def tokenize_chinese_aware(text: str) -> list[str]:
    """
    Chinese-aware tokenization using jieba for better BM25 performance.

    Falls back to basic tokenization if jieba is not available.

    Args:
        text: Input text (Chinese or English)

    Returns:
        List of tokens

    Examples:
        >>> tokenize_chinese_aware("\u673a\u5668\u5b66\u4e60\u7b97\u6cd5")
        ["\u673a\u5668", "\u5b66\u4e60", "\u7b97\u6cd5"]  # With jieba
        >>> tokenize_chinese_aware("machine learning")
        ["machine", "learning"]
    """
    if not text:
        return []

    text_lower = text.lower()

    # Try to use jieba for Chinese text segmentation
    try:
        import jieba

        # Detect if text contains significant Chinese content (>20% Chinese chars)
        chinese_char_count = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        total_chars = len([c for c in text if not c.isspace()])

        if total_chars > 0 and chinese_char_count / total_chars > 0.2:
            # Use jieba for Chinese text
            tokens = list(jieba.cut_for_search(text_lower))
            # Filter out single-character tokens and whitespace
            return [t.strip() for t in tokens if t.strip() and len(t.strip()) > 1]

    except ImportError:
        pass  # Fall back to basic tokenization

    # For English or when jieba is not available
    return TOKEN_PATTERN.findall(text_lower)


@lru_cache(maxsize=1)
def _load_bm25(use_chinese_tokenizer: bool = True):
    """
    Load BM25 index with optional Chinese-aware tokenization.

    Args:
        use_chinese_tokenizer: If True, use jieba for Chinese text (default: True)

    Returns:
        Tuple of (BM25Okapi instance, corpus records)
    """
    records = read_corpus_records()

    # Choose tokenizer based on configuration
    tokenizer_func = tokenize_chinese_aware if use_chinese_tokenizer else tokenize
    tokenized = [tokenizer_func(r.get("text", "")) for r in records]

    if not tokenized:
        return None, []
    if BM25Okapi is None:
        return None, records
    return BM25Okapi(tokenized), records


def bm25_search(
    query: str, k: int = 6, allowed_sources: list[str] | None = None, use_chinese_tokenizer: bool = True
) -> list[dict]:
    """
    Perform BM25 search with optional Chinese-aware tokenization.

    Args:
        query: Search query
        k: Number of results to return
        allowed_sources: Optional list of allowed source files
        use_chinese_tokenizer: Use jieba for Chinese text (default: True)

    Returns:
        List of ranked documents with BM25 scores
    """
    bm25, records = _load_bm25(use_chinese_tokenizer=use_chinese_tokenizer)
    if not records:
        return []

    # Filter by allowed_sources if specified
    if allowed_sources is not None:
        allowed = set(allowed_sources)
        filtered_records = [r for r in records if str((r.get("metadata", {}) or {}).get("source", "")) in allowed]
        if not filtered_records:
            return []

        # Rebuild BM25 index with filtered records
        tokenizer_func = tokenize_chinese_aware if use_chinese_tokenizer else tokenize
        if BM25Okapi is None:
            bm25 = None
            records = filtered_records
        else:
            tokenized = [tokenizer_func(r.get("text", "")) for r in filtered_records]
            if not tokenized:
                return []
            bm25 = BM25Okapi(tokenized)
            records = filtered_records

    # Tokenize query with the same tokenizer
    tokenizer_func = tokenize_chinese_aware if use_chinese_tokenizer else tokenize
    tokens = tokenizer_func(query)

    if not tokens:
        return []

    if bm25 is None:
        # Fallback: simple token overlap scoring
        query_set = set(tokens)
        scored = []
        for idx, row in enumerate(records):
            doc_tokens = set(tokenizer_func(row.get("text", "")))
            score = len(query_set.intersection(doc_tokens))
            scored.append((idx, float(score)))
        scores = [x[1] for x in sorted(scored, key=lambda x: x[0])]
    else:
        scores = bm25.get_scores(tokens)

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
    return [
        {
            "id": records[idx]["id"],
            "text": records[idx]["text"],
            "metadata": records[idx].get("metadata", {}),
            "bm25_score": float(score),
        }
        for idx, score in ranked
        if score > 0
    ]


def reset_bm25_cache() -> None:
    """Clear the BM25 index cache to force reloading."""
    _load_bm25.cache_clear()
