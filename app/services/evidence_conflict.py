from __future__ import annotations

import re
from typing import Any

_NEGATIVE = {"not", "no", "never", "cannot", "can't", "without", "未", "不", "没有", "无法"}


def detect_evidence_conflict(citations: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [str((c or {}).get("content", "") or "").strip() for c in citations if str((c or {}).get("content", "") or "").strip()]
    if len(texts) < 2:
        return {"conflict": False, "score": 0.0, "pairs_checked": 0}
    pairs = 0
    conflict_hits = 0
    snippets: list[str] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a = texts[i]
            b = texts[j]
            pairs += 1
            if _is_conflicting_pair(a, b):
                conflict_hits += 1
                if len(snippets) < 3:
                    snippets.append(f"{_trim(a)} <> {_trim(b)}")
    score = (conflict_hits / pairs) if pairs else 0.0
    return {
        "conflict": score >= 0.25 and conflict_hits > 0,
        "score": round(score, 4),
        "pairs_checked": pairs,
        "conflict_hits": conflict_hits,
        "examples": snippets,
    }


def _is_conflicting_pair(a: str, b: str) -> bool:
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


def _shared_keywords(a: str, b: str) -> set[str]:
    a_tokens = {x for x in re.findall(r"[a-zA-Z_]{4,}", a)}
    b_tokens = {x for x in re.findall(r"[a-zA-Z_]{4,}", b)}
    return {x for x in (a_tokens & b_tokens) if x not in {"this", "that", "with", "from", "have", "will", "should"}}


def _trim(text: str, limit: int = 64) -> str:
    s = " ".join(text.split())
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."
