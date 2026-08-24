"""Lightweight offline RAG quality metrics over governed evidence."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.domain.contracts import EvidenceItem

_TOKEN_RE = re.compile(r"[a-z0-9_-]{2,}|[\u4e00-\u9fff]", re.IGNORECASE)
_CLAIM_RE = re.compile(r"[^。！？.!?\n]+[。！？.!?]?", re.MULTILINE)


def faithfulness(answer: str, evidence: Sequence[EvidenceItem], *, support_threshold: float = 0.35) -> float:
    """Estimate the fraction of answer claims lexically supported by retrieved context."""

    claims = [claim.strip() for claim in _CLAIM_RE.findall(_without_citations(answer)) if claim.strip()]
    if not claims:
        return 0.0
    context_tokens = _tokens("\n".join(item.content for item in evidence))
    if not context_tokens:
        return 0.0
    supported = sum(1 for claim in claims if _overlap(_tokens(claim), context_tokens) >= support_threshold)
    return supported / len(claims)


def answer_relevance(question: str, answer: str) -> float:
    """Estimate whether the answer addresses the query using normalized token overlap."""

    query_tokens = _tokens(question)
    answer_tokens = _tokens(_without_citations(answer))
    return _overlap(query_tokens, answer_tokens)


def citation_coverage(answer: str) -> float:
    """Return the fraction of non-empty claims carrying an ``[E#]`` citation marker."""

    claims = [claim.strip() for claim in _CLAIM_RE.findall(answer) if claim.strip()]
    if not claims:
        return 0.0
    cited = sum(1 for claim in claims if re.search(r"\[E\d+\]", claim))
    return cited / len(claims)


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(str(text or ""))}


def _overlap(expected: set[str], actual: set[str]) -> float:
    return len(expected.intersection(actual)) / len(expected) if expected else 0.0


def _without_citations(text: str) -> str:
    return re.sub(r"\[E\d+\]", "", str(text or ""))


__all__ = ["answer_relevance", "citation_coverage", "faithfulness"]
