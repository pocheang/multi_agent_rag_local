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


# How many distinct access scopes keep a prebuilt index. Each entry holds only
# that scope's own records, so this is bounded by concurrent users, not corpus
# size.
SCOPED_INDEX_CACHE_SIZE = 32


def _build_index(records: list[dict], use_chinese_tokenizer: bool):
    """Tokenize records once and build the BM25 index over them.

    The per-document token sets are kept alongside the index because matching
    ("does this document contain a query term?") and ranking ("how well?") are
    separate questions -- see bm25_search. Retokenizing per query would undo the
    point of caching the index.
    """
    tokenizer_func = tokenize_chinese_aware if use_chinese_tokenizer else tokenize
    tokenized = [tokenizer_func(r.get("text", "")) for r in records]
    if not tokenized:
        return None, [], []
    token_sets = [frozenset(tokens) for tokens in tokenized]
    if BM25Okapi is None:
        return None, records, token_sets
    return BM25Okapi(tokenized), records, token_sets


@lru_cache(maxsize=1)
def _load_bm25(use_chinese_tokenizer: bool = True):
    """
    Load BM25 index with optional Chinese-aware tokenization.

    Args:
        use_chinese_tokenizer: If True, use jieba for Chinese text (default: True)

    Returns:
        Tuple of (BM25Okapi instance, corpus records, per-record token sets)
    """
    return _build_index(read_corpus_records(), use_chinese_tokenizer)


@lru_cache(maxsize=SCOPED_INDEX_CACHE_SIZE)
def _load_scoped_bm25(allowed: tuple[str, ...], use_chinese_tokenizer: bool = True):
    """Build (and keep) the BM25 index for one access scope.

    Scoping used to re-filter the whole corpus and rebuild the index on *every*
    query. The result was correct but paid an O(corpus) scan plus a full index
    build per question, so a user asking three questions in a row rebuilt their
    index three times. Keyed on the scope's own source list, a repeat question
    from the same user now reuses the index.
    """
    _bm25, records, _token_sets = _load_bm25(use_chinese_tokenizer=use_chinese_tokenizer)
    if not records:
        return None, [], []
    permitted = set(allowed)
    scoped = [row for row in records if str((row.get("metadata", {}) or {}).get("source", "")) in permitted]
    if not scoped:
        return None, [], []
    return _build_index(scoped, use_chinese_tokenizer)


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
    if allowed_sources is None:
        # Same contract as similarity_search: a missing scope is a caller that
        # skipped the resolver, not a licence to read every tenant's corpus.
        raise ValueError(
            "allowed_sources is required for user data isolation. "
            "Pass the caller's resolved scope; an empty list means 'no documents'."
        )
    bm25, records, token_sets = _load_scoped_bm25(tuple(sorted(allowed_sources)), use_chinese_tokenizer)
    if not records:
        return []

    # Tokenize query with the same tokenizer
    tokenizer_func = tokenize_chinese_aware if use_chinese_tokenizer else tokenize
    tokens = tokenizer_func(query)

    if not tokens:
        return []

    # Match on term overlap, rank by BM25 -- two separate questions.
    #
    # This used to keep whatever scored above zero, which is only a proxy for
    # "contains a query term" and a proxy that inverts on a small index: BM25 IDF
    # goes negative for a term present in most documents, so in a one-document
    # scope *every* term scores negative and a matching document was dropped. A
    # user whose whole corpus was one chunk got no BM25 hits at all -- and
    # per-scope indexes make small scopes the common case, not the exception.
    query_terms = set(tokens)
    matched = [index for index, terms in enumerate(token_sets) if query_terms & terms]
    if not matched:
        return []

    if bm25 is None:
        # Fallback ranking when rank_bm25 is unavailable: term overlap count.
        scores = {index: float(len(query_terms & token_sets[index])) for index in matched}
    else:
        raw = bm25.get_scores(tokens)
        scores = {index: float(raw[index]) for index in matched}

    ranked = sorted(matched, key=lambda index: scores[index], reverse=True)[:k]
    return [
        {
            "id": records[index]["id"],
            "text": records[index]["text"],
            "metadata": records[index].get("metadata", {}),
            "bm25_score": scores[index],
        }
        for index in ranked
    ]


def reset_bm25_cache() -> None:
    """Clear the BM25 index caches to force reloading."""
    _load_bm25.cache_clear()
    _load_scoped_bm25.cache_clear()
