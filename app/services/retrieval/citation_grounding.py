import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_CJK_PUNCTUATION_CLASS = "\u3002\uFF01\uFF1F"
_ABBREVIATIONS = {
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "sr.",
    "jr.",
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "inc.",
    "ltd.",
    "corp.",
    "fig.",
    "vol.",
    "no.",
    "p.",
    "pp.",
    "ed.",
}
_HEDGE_MARKERS = (
    "\u53ef\u80fd",
    "\u6216\u8bb8",
    "\u5927\u6982\u7387",
    "\u6839\u636e\u73b0\u6709\u4fe1\u606f",
    "\u76ee\u524d\u65e0\u6cd5\u786e\u8ba4",
    "insufficient evidence",
    "likely",
)
_LOW_SUPPORT_PREFIX = "\u57fa\u4e8e\u5f53\u524d\u53ef\u7528\u8bc1\u636e\uff0c"


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _split_sentences(text: str) -> list[str]:
    raw_text = str(text or "").strip()
    if not raw_text:
        return []

    protected_text = raw_text
    for abbr in _ABBREVIATIONS:
        protected_text = protected_text.replace(abbr, abbr.replace(".", "<ABBR>"))
        protected_text = protected_text.replace(abbr.upper(), abbr.upper().replace(".", "<ABBR>"))

    chunks = re.findall(rf"[^{_CJK_PUNCTUATION_CLASS}.!?]+[{_CJK_PUNCTUATION_CLASS}.!?]?", protected_text)
    sentences: list[str] = []
    for chunk in chunks:
        restored = chunk.replace("<ABBR>", ".")
        cleaned = restored.strip()
        if len(cleaned) >= 3:
            sentences.append(cleaned)

    return sentences if sentences else [raw_text]


def _support_score(sentence: str, evidence_tokens: set[str]) -> float:
    st = _tokenize(sentence)
    if not st or not evidence_tokens:
        return 0.0
    return len(st & evidence_tokens) / max(1, len(st))


def _has_hedge(text: str) -> bool:
    lower = str(text or "").lower()
    return any(marker.lower() in lower for marker in _HEDGE_MARKERS)


def _rewrite_low_support_sentence(sentence: str) -> str:
    if sentence.startswith(_LOW_SUPPORT_PREFIX) or _has_hedge(sentence):
        return sentence
    return f"{_LOW_SUPPORT_PREFIX}{sentence}"


def apply_sentence_grounding(
    answer: str,
    evidence_texts: list[str],
    threshold: float = 0.22,
) -> tuple[str, dict]:
    sentences = _split_sentences(answer)
    evid_tokens = _tokenize("\n".join([x for x in evidence_texts if x]))

    if not sentences:
        return answer, {"enabled": False, "reason": "no_sentences", "total_sentences": 0}
    if not evid_tokens:
        return answer, {"enabled": False, "reason": "no_evidence", "total_sentences": len(sentences)}

    supported = 0
    rewritten = 0
    low_support_examples: list[str] = []
    grounded_sentences: list[str] = []

    for sent in sentences:
        score = _support_score(sent, evid_tokens)
        if score >= threshold or _has_hedge(sent):
            supported += 1
            grounded_sentences.append(sent)
            continue

        rewritten += 1
        low_support_examples.append(sent[:120])
        grounded_sentences.append(_rewrite_low_support_sentence(sent))

    joiner = "" if re.search(r"[\u4e00-\u9fff]", answer or "") else " "
    grounded_answer = joiner.join(grounded_sentences)
    report = {
        "enabled": True,
        "reason": "sentence_grounding",
        "total_sentences": len(sentences),
        "supported_sentences": supported,
        "support_ratio": (supported / len(sentences)) if sentences else 0.0,
        "rewritten_sentences": rewritten,
        "low_support_examples": low_support_examples[:3],
    }
    return grounded_answer, report
