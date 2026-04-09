import re

from app.core.models import get_chat_model, get_reasoning_model

_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{2,}|[\u4e00-\u9fff]{2,}")
_STOPWORDS = {
    "the",
    "is",
    "are",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "for",
    "and",
    "or",
    "请问",
    "帮我",
    "一下",
    "这个",
    "那个",
}


def _rule_keywords(query: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    for token in _TOKEN_RE.findall((query or "").lower()):
        if token in _STOPWORDS:
            continue
        if token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def _decompose_query(query: str, max_parts: int = 3) -> list[str]:
    q = str(query or "").strip()
    if not q:
        return []
    parts: list[str] = []
    for seg in re.split(r"[，,。；;！？?!\n]|(?:\band\b|\bor\b|以及|并且|同时|还有)", q, flags=re.IGNORECASE):
        item = seg.strip()
        if len(item) >= 4 and item.lower() != q.lower():
            parts.append(item)
        if len(parts) >= max_parts:
            break
    return parts


def _rule_rewrites(query: str) -> list[str]:
    q = str(query or "").strip()
    if not q:
        return []
    rewrites = [q]
    kw = _rule_keywords(q)
    if len(kw) >= 2:
        compact = " ".join(kw)
        if compact != q:
            rewrites.append(compact)
        short_kw = " ".join(kw[: max(2, min(4, len(kw) - 1))]).strip()
        if short_kw and short_kw.lower() != q.lower() and short_kw not in rewrites:
            rewrites.append(short_kw)
    return rewrites


def _llm_rewrite(query: str, use_reasoning: bool = False) -> str | None:
    prompt = (
        "Rewrite the query for retrieval. Keep meaning unchanged. "
        "Return one short rewritten query only."
    )
    try:
        model = get_reasoning_model() if use_reasoning else get_chat_model()
        result = model.invoke([("system", prompt), ("human", query)])
        text = (result.content if hasattr(result, "content") else str(result)).strip()
        if not text or len(text) < 3:
            return None
        return text.replace("\n", " ").strip()
    except Exception:
        return None


def build_rewrite_queries(
    query: str,
    enable_llm: bool = False,
    use_reasoning: bool = False,
    enable_decompose: bool = True,
    max_variants: int = 6,
) -> list[str]:
    rewrites = _rule_rewrites(query)
    if enable_decompose:
        rewrites.extend(_decompose_query(query))
    if enable_llm:
        llm_q = _llm_rewrite(query, use_reasoning=use_reasoning)
        if llm_q and llm_q not in rewrites:
            rewrites.append(llm_q)
    # dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for item in rewrites:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if len(out) >= max_variants:
            break
    return out
