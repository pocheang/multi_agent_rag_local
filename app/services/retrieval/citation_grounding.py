import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_CJK_PUNCTUATION_CLASS = "\u3002\uff01\uff1f"
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


_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
"""A dot inside a URL is not a sentence boundary."""

# Anchored on a non-alphanumeric boundary, and longest-first so "pp." wins over
# "p.". Without the lookbehind these were plain substrings: `"p."` matched inside
# "setup.", `"ed."` inside "used." / "based." / "updated." / "required.", `"no."`
# inside "casino.". Those are ordinary English sentence endings, so the sentence
# did not split there -- a whole paragraph was scored as one claim -- and the
# offsets shifted, which is the other half of the bug below.
_ABBREVIATION_RE = re.compile(
    "(?<![A-Za-z0-9])(?:" + "|".join(re.escape(a) for a in sorted(_ABBREVIATIONS, key=len, reverse=True)) + ")",
    re.IGNORECASE,
)

# One character, so protection is length-preserving and an offset in the
# protected string is the same offset in the original. It used to be "<ABBR>",
# six characters replacing one, while a comment beside the offsets asserted the
# substitution was the same length -- and `apply_sentence_grounding` splices its
# edits into the *raw* answer by those offsets. Measured on
# "Access is based. The retention window is ninety days. Backups run nightly."
# the hedge landed five characters into the last sentence:
# "... days. Backu基于当前可用证据，Backups run nightly."
#
# U+E000 is the first Private Use Area code point: it has no meaning, no
# renderer will produce it, and nothing upstream can legitimately contain it.
_ABBR_DOT = chr(0xE000)


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """Sentences with their offsets in the original string.

    Offsets, not just the strings, because the caller has to put the answer back
    together. Rejoining the pieces with a single separator reflows the whole
    answer onto whatever that separator is -- paragraph breaks, list indentation
    and the spacing around citation markers all become one space (or, for a
    Chinese answer, nothing at all). Replacing only the spans that changed keeps
    every character the generator wrote and that no rule objected to.
    """
    raw_text = str(text or "")
    if not raw_text.strip():
        return []

    # Case-insensitive and boundary-anchored, so "Dr." is protected (the old loop
    # tried only the lower and upper forms, missing the ordinary capitalisation)
    # and "based." is not (the old loop matched "ed." as a bare substring).
    protected_text = _ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", _ABBR_DOT), raw_text)
    # A dot inside a URL is not a sentence boundary, and treating it as one does
    # not merely mis-split: the fragment after it scores as unsupported and gets
    # the hedge spliced into the middle of the link
    # (`https://x.基于当前可用证据，example/a`), which breaks the citation the
    # sentence was carrying. Same length substitution, so offsets are unaffected.
    protected_text = _URL_RE.sub(lambda m: m.group(0).replace(".", _ABBR_DOT), protected_text)

    spans: list[tuple[int, int, str]] = []
    # A blank line always ends a sentence, whatever punctuation did or did not
    # precede it. Without this a heading, a list item and the paragraph above
    # them merge into one fragment, which is then judged -- and rewritten -- as
    # though it were a single claim.
    body = rf"[^{_CJK_PUNCTUATION_CLASS}.!?\n]"
    pattern = (
        f"{body}+"
        rf"(?:\n(?!\s*\n){body}*)*"
        rf"[{_CJK_PUNCTUATION_CLASS}.!?]?"
    )
    for match in re.finditer(pattern, protected_text):
        chunk = match.group(0)
        stripped = chunk.strip()
        if len(stripped) < 3:
            continue
        # The offsets are valid because `_ABBR_DOT` is one character, exactly
        # like the "." it replaced, so protection never shifts a position. That
        # sentence was here before and was false: the sentinel was "<ABBR>".
        start = match.start() + (len(chunk) - len(chunk.lstrip()))
        spans.append((start, start + len(stripped), stripped.replace(_ABBR_DOT, ".")))

    return spans if spans else [(0, len(raw_text), raw_text.strip())]


def _support_score(sentence: str, evidence_tokens: set[str]) -> float:
    st = _tokenize(sentence)
    if not st or not evidence_tokens:
        return 0.0
    return len(st & evidence_tokens) / max(1, len(st))


def _has_hedge(text: str) -> bool:
    lower = str(text or "").lower()
    return any(marker.lower() in lower for marker in _HEDGE_MARKERS)


_HEADING_MAX_CHARS = 20
"""Above this, an unpunctuated fragment is prose that lost its full stop
rather than a section title, and hedging it is the safer error."""

_DECORATION_RE = re.compile(r"\*+|_{2,}|^#+\s*|\[[^\]]*\]|`")
"""Markdown emphasis, heading marks and citation markers."""

_CLAIMLESS_RE = re.compile(rf"^(?:\[[^\]]*\]|[\s{_CJK_PUNCTUATION_CLASS}.,!?;:()\-—·*_#>]+)+$")


def _makes_a_claim(sentence: str) -> bool:
    """Whether this fragment asserts anything that could lack support.

    A citation marker on its own does not. `_sentence_spans` hands back `[E2]`
    as a sentence whenever a paragraph ends on one, and a bare marker shares no
    tokens with the evidence, so it scored as unsupported and came back as
    "基于当前可用证据，[E2]" -- hedging the attribution rather than the claim, and
    reading as though the citation itself were doubtful. Reference-list lines and
    bare headings fail this the same way and for the same reason.
    """
    stripped = sentence.strip()
    if _CLAIMLESS_RE.match(stripped):
        return False
    # Structure, not prose: a heading names a section, it does not assert
    # anything, so qualifying it produces "**基于当前可用证据，参考来源**". Judged by
    # shape rather than by a list of known headings, which would only work in
    # the two languages someone thought of.
    # URLs come out too: a link is a locator, not an assertion, so a line that
    # is only a citation and its URL has nothing to qualify.
    bare = _URL_RE.sub("", _DECORATION_RE.sub("", stripped)).strip()
    if not bare:
        return False
    # Length in characters, not tokens: `_TOKEN_RE` counts CJK per character, so
    # any word-count threshold means something different in each script -- a
    # four-character Chinese heading outscored a two-word English one.
    ends_a_sentence = bool(re.search(rf"[{_CJK_PUNCTUATION_CLASS}.!?]$", bare))
    return ends_a_sentence or len(bare) > _HEADING_MAX_CHARS


_LEAD_IN_RE = re.compile(r"^(?:\s|[-*+>#]|\d+[.)]|\[[^\]]*\])+")


def _rewrite_low_support_sentence(sentence: str) -> str:
    """Hedge the claim, not whatever happens to precede it.

    A fragment can open with a citation marker carried over from the previous
    paragraph, a list bullet, or a heading mark. Prefixing the raw string puts
    the qualifier in front of those -- "基于当前可用证据，[E1]" reads as doubt about
    the citation, and "基于当前可用证据，- item" is not a sentence at all.
    """
    if sentence.startswith(_LOW_SUPPORT_PREFIX) or _has_hedge(sentence):
        return sentence
    lead = _LEAD_IN_RE.match(sentence)
    cut = lead.end() if lead else 0
    return f"{sentence[:cut]}{_LOW_SUPPORT_PREFIX}{sentence[cut:]}"


def apply_sentence_grounding(
    answer: str,
    evidence_texts: list[str],
    threshold: float = 0.22,
) -> tuple[str, dict]:
    spans = _sentence_spans(answer)
    evid_tokens = _tokenize("\n".join([x for x in evidence_texts if x]))

    if not spans:
        return answer, {"enabled": False, "reason": "no_sentences", "total_sentences": 0}
    if not evid_tokens:
        return answer, {"enabled": False, "reason": "no_evidence", "total_sentences": len(spans)}

    supported = 0
    rewritten = 0
    claimless = 0
    low_support_examples: list[str] = []
    edits: list[tuple[int, int, str]] = []

    for start, end, sent in spans:
        if not _makes_a_claim(sent):
            claimless += 1
            continue
        score = _support_score(sent, evid_tokens)
        if score >= threshold or _has_hedge(sent):
            supported += 1
            continue

        rewritten += 1
        low_support_examples.append(sent[:120])
        edits.append((start, end, _rewrite_low_support_sentence(sent)))

    # Rebuild by splicing, so untouched text keeps the exact whitespace it had.
    grounded_answer = answer
    for start, end, replacement in reversed(edits):
        grounded_answer = grounded_answer[:start] + replacement + grounded_answer[end:]
    sentences = [sent for _, _, sent in spans]
    report = {
        "enabled": True,
        "reason": "sentence_grounding",
        "total_sentences": len(sentences),
        "supported_sentences": supported,
        "support_ratio": (supported / len(sentences)) if sentences else 0.0,
        "rewritten_sentences": rewritten,
        "claimless_fragments": claimless,
        "low_support_examples": low_support_examples[:3],
    }
    return grounded_answer, report
