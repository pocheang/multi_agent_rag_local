import re
from functools import lru_cache

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - optional dependency fallback
    BM25Okapi = None  # type: ignore[assignment]

from app.retrievers.corpus_store import read_corpus_records

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


@lru_cache(maxsize=1)
def _load_bm25():
    records = read_corpus_records()
    tokenized = [tokenize(r.get("text", "")) for r in records]
    if not tokenized:
        return None, []
    if BM25Okapi is None:
        return None, records
    return BM25Okapi(tokenized), records


def bm25_search(query: str, k: int = 6, allowed_sources: list[str] | None = None) -> list[dict]:
    bm25, records = _load_bm25()
    if not records:
        return []
    if allowed_sources is not None:
        allowed = set(allowed_sources)
        records = [r for r in records if str((r.get("metadata", {}) or {}).get("source", "")) in allowed]
        if not records:
            return []
        if BM25Okapi is None:
            bm25 = None
        else:
            tokenized = [tokenize(r.get("text", "")) for r in records]
            bm25 = BM25Okapi(tokenized) if tokenized else None
    tokens = tokenize(query)
    if bm25 is None:
        query_set = set(tokens)
        scored = []
        for idx, row in enumerate(records):
            score = len(query_set.intersection(set(tokenize(row.get("text", "")))))
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
    _load_bm25.cache_clear()
