from __future__ import annotations

import re
from typing import Any

_NEGATIVE = {"not", "no", "never", "cannot", "can't", "without", "未", "不", "没有", "无法"}

# Maximum pairs to check (early exit optimization for large citation sets)
_MAX_PAIRS_TO_CHECK = 100


def detect_evidence_conflict(citations: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [
        str((c or {}).get("content", "") or "").strip()
        for c in citations
        if str((c or {}).get("content", "") or "").strip()
    ]
    if len(texts) < 2:
        return {"conflict": False, "score": 0.0, "pairs_checked": 0}

    # OPTIMIZATION: Pre-tokenize all texts once (avoids re-tokenization in _shared_keywords)
    tokenized_texts = [_tokenize(text.lower()) for text in texts]
    has_neg_cache = [_has_neg(text.lower()) for text in texts]

    pairs = 0
    conflict_hits = 0
    snippets: list[str] = []
    max_snippets = 3

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            # OPTIMIZATION: Early exit if we've checked enough pairs
            if pairs >= _MAX_PAIRS_TO_CHECK:
                break

            pairs += 1
            a_tokens = tokenized_texts[i]
            b_tokens = tokenized_texts[j]

            # Check for shared keywords (using pre-tokenized sets)
            shared = a_tokens & b_tokens
            if not shared:
                continue

            # Check negation (using cached results)
            a_neg = has_neg_cache[i]
            b_neg = has_neg_cache[j]

            if a_neg != b_neg:
                conflict_hits += 1
                # OPTIMIZATION: Early exit once we have enough examples
                if len(snippets) < max_snippets:
                    snippets.append(f"{_trim(texts[i])} <> {_trim(texts[j])}")
                # OPTIMIZATION: Early exit if we've found strong evidence of conflict
                elif conflict_hits >= 5 and (conflict_hits / pairs) >= 0.3:
                    break

        # Break outer loop too if we hit the limit
        if pairs >= _MAX_PAIRS_TO_CHECK:
            break

    score = (conflict_hits / pairs) if pairs else 0.0
    return {
        "conflict": score >= 0.25 and conflict_hits > 0,
        "score": round(score, 4),
        "pairs_checked": pairs,
        "conflict_hits": conflict_hits,
        "examples": snippets,
    }


def _is_conflicting_pair(a: str, b: str) -> bool:
    """Legacy function kept for compatibility (not used in optimized path)."""
    a_l = a.lower()
    b_l = b.lower()
    shared = _shared_keywords(a_l, b_l)
    if not shared:
        return False
    a_neg = _has_neg(a_l)
    b_neg = _has_neg(b_l)
    return a_neg != b_neg


def _has_neg(text: str) -> bool:
    for token in _NEGATIVE:
        if token in text:
            return True
    return False


def _tokenize(text: str) -> set[str]:
    """Tokenize text and filter out common stop words (used for caching)."""
    tokens = {x for x in re.findall(r"[a-zA-Z_]{4,}", text)}
    # Filter stop words
    return {x for x in tokens if x not in {"this", "that", "with", "from", "have", "will", "should"}}


def _shared_keywords(a: str, b: str) -> set[str]:
    """Legacy function kept for compatibility (prefer _tokenize for caching)."""
    a_tokens = _tokenize(a)
    b_tokens = _tokenize(b)
    return a_tokens & b_tokens


def _trim(text: str, limit: int = 64) -> str:
    s = " ".join(text.split())
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."
