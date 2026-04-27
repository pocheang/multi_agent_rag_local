import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]")

# Improved sentence splitting that handles common abbreviations and edge cases
_SENTENCE_SPLIT_RE = re.compile(
    r'(?<=[。！？])'  # After Chinese punctuation
    r'|(?<=[.!?])'   # After English punctuation
    r'(?![.!?])'     # Not followed by more punctuation (handles ellipsis)
    r'(?!\s*["\'])'  # Not followed by closing quote
    r'(?!\s*\))'     # Not followed by closing parenthesis
    r'(?!\s+[a-z])'  # Not followed by lowercase (handles abbreviations like "Dr. Smith")
)

# Common abbreviations that should not trigger sentence breaks
_ABBREVIATIONS = {
    'dr.', 'mr.', 'mrs.', 'ms.', 'prof.', 'sr.', 'jr.',
    'e.g.', 'i.e.', 'etc.', 'vs.', 'inc.', 'ltd.', 'corp.',
    'fig.', 'vol.', 'no.', 'p.', 'pp.', 'ed.',
}

_HEDGE_MARKERS = ("可能", "或许", "大概率", "根据现有信息", "目前无法确认", "insufficient evidence", "likely")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences with improved handling of abbreviations and edge cases.
    """
    raw_text = str(text or "").strip()
    if not raw_text:
        return []

    # Pre-process: protect abbreviations by temporarily replacing periods
    protected_text = raw_text
    for abbr in _ABBREVIATIONS:
        # Replace "Dr." with "Dr<ABBR>" temporarily
        protected_text = protected_text.replace(abbr, abbr.replace('.', '<ABBR>'))
        protected_text = protected_text.replace(abbr.upper(), abbr.upper().replace('.', '<ABBR>'))

    # Split sentences
    raw_sentences = _SENTENCE_SPLIT_RE.split(protected_text)

    # Post-process: restore abbreviations and clean up
    sentences = []
    for sent in raw_sentences:
        # Restore abbreviations
        restored = sent.replace('<ABBR>', '.')
        cleaned = restored.strip()

        # Skip empty or very short fragments
        if len(cleaned) < 3:
            continue

        # Merge fragments that don't end with proper punctuation back to previous sentence
        # But only if previous sentence exists and current fragment is not too long
        if sentences and cleaned and cleaned[-1] not in '。！？.!?' and len(cleaned) < 100:
            sentences[-1] = sentences[-1] + ' ' + cleaned
        else:
            sentences.append(cleaned)

    # Fallback: if splitting produced no valid sentences, return original text as single sentence
    return sentences if sentences else [raw_text]


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
    if not sentences:
        return answer, {"enabled": False, "reason": "no_sentences", "total_sentences": 0}
    if not evid_tokens:
        return answer, {"enabled": False, "reason": "no_evidence", "total_sentences": len(sentences)}

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
        # Add hedge prefix, but preserve sentence structure
        # Handle both Chinese and English sentences
        if sent and sent[0] in '。！？.!?':
            # Sentence starts with punctuation (edge case), just prepend
            rewritten.append(f"基于当前可用证据，{sent}")
        else:
            rewritten.append(f"基于当前可用证据，{sent}")

    # Join sentences with proper spacing
    grounded = " ".join(rewritten).strip()
    # Clean up multiple spaces
    grounded = re.sub(r'\s+', ' ', grounded)

    report = {
        "enabled": True,
        "total_sentences": len(sentences),
        "supported_sentences": supported,
        "support_ratio": (supported / len(sentences)),
        "low_support_examples": low_support_examples[:3],
    }
    return grounded or answer, report
