import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s+|(?<=[。！？.!?])")
_HEDGE_MARKERS = ("可能", "或许", "大概率", "根据现有信息", "目前无法确认", "insufficient evidence", "likely")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _split_sentences(text: str) -> list[str]:
    raw = [x.strip() for x in _SENTENCE_SPLIT_RE.split(str(text or "").strip()) if x.strip()]
    return raw if raw else ([str(text or "").strip()] if str(text or "").strip() else [])


def _support_score(sentence: str, evidence_tokens: set[str]) -> float:
    st = _tokenize(sentence)
    if not st or not evidence_tokens:
        return 0.0
    return len(st & evidence_tokens) / max(1, len(st))


def _has_hedge(text: str) -> bool:
    lower = str(text or "").lower()
    return any(m.lower() in lower for m in _HEDGE_MARKERS)


def apply_sentence_grounding(
    answer: str,
    evidence_texts: list[str],
    threshold: float = 0.22,
) -> tuple[str, dict]:
    sentences = _split_sentences(answer)
    evid_tokens = _tokenize("\n".join([x for x in evidence_texts if x]))
    if not sentences or not evid_tokens:
        return answer, {"enabled": False, "reason": "no_evidence_or_empty_answer", "total_sentences": len(sentences)}

    supported = 0
    rewritten: list[str] = []
    low_support_examples: list[str] = []
    for sent in sentences:
        score = _support_score(sent, evid_tokens)
        if score >= threshold:
            supported += 1
            rewritten.append(sent)
            continue
        if _has_hedge(sent):
            rewritten.append(sent)
            continue
        low_support_examples.append(sent[:120])
        rewritten.append(f"基于当前可用证据，{sent}")

    grounded = "".join(rewritten).strip()
    report = {
        "enabled": True,
        "total_sentences": len(sentences),
        "supported_sentences": supported,
        "support_ratio": (supported / max(1, len(sentences))),
        "low_support_examples": low_support_examples[:3],
    }
    return grounded or answer, report
