import logging
import re
from collections.abc import Sequence

from app.services.models.runtime import get_chat_model, get_reasoning_model

_REWRITE_CONTEXT_TURNS = 6
"""Three rounds, matching SHORT_TERM_ROUNDS: a follow-up refers to the recent
turns, and older ones only dilute the prompt."""

logger = logging.getLogger(__name__)

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


_STANDALONE_PROMPT = """You rewrite a follow-up question into a standalone one for document retrieval.

Rules:
- Replace pronouns and omitted subjects with what the conversation shows they refer to.
  Chinese follow-ups routinely drop the subject entirely ("成本呢？"), which is the main
  case this exists for -- there is no pronoun to replace, only a subject to restore.
- Change nothing else. Do not answer, expand, translate, or add terms the user did not use.
- If the question already stands on its own, return it unchanged.
- If the conversation does not show what it refers to, return it unchanged rather than
  guessing: a wrong subject retrieves confidently for the wrong thing, which is worse than
  retrieving vaguely for the right one.
Return one short question and nothing else."""


def _render_turns(conversation: Sequence[object]) -> str:
    """Render turns for the rewrite prompt, oldest first, newest last.

    Only user and assistant turns: a `system` turn on this path carries the
    already-rendered memory block, which is a summary of these same rounds plus
    long-term memories. Feeding it back in would show the model the same content
    twice in two formats and crowd out the turns that actually establish what the
    follow-up refers to.
    """
    lines: list[str] = []
    for turn in conversation:
        role = str(getattr(turn, "role", "") or "").strip().lower()
        content = str(getattr(turn, "content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines[-_REWRITE_CONTEXT_TURNS:])


def _llm_rewrite(query: str, conversation: Sequence[object] = (), use_reasoning: bool = False) -> str | None:
    from app.services.runtime.request_context import deadline_exceeded, remaining_seconds

    # Check if we have time for LLM rewrite
    if deadline_exceeded():
        return None

    timeout = remaining_seconds()
    if timeout is None or timeout < 0.5:
        # Not enough time for LLM call
        return None

    # Reserve at least 0.5s for the rest of the pipeline
    timeout = max(0.5, min(2.0, timeout - 0.5))

    history = _render_turns(conversation)
    prompt = (
        _STANDALONE_PROMPT
        if history
        else "Rewrite the query for retrieval. Keep meaning unchanged. Return one short rewritten query only."
    )
    try:
        model = get_reasoning_model() if use_reasoning else get_chat_model()
        # The timeout is enforced by request_context, which the engine now opens
        # for the whole workflow; before that it was never set on this path and
        # `remaining_seconds()` above returned None on every request.
        human = f"Conversation:\n{history}\n\nFollow-up question: {query}" if history else query
        result = model.invoke([("system", prompt), ("human", human)])
        text = (result.content if hasattr(result, "content") else str(result)).strip()
        if not text or len(text) < 3:
            return None
        return text.replace("\n", " ").strip()
    except (RuntimeError, ValueError, TypeError) as e:
        logger.debug(f"Query rewrite failed: {e}")
        return None


def build_rewrite_queries(
    query: str,
    enable_llm: bool = False,
    use_reasoning: bool = False,
    enable_decompose: bool = True,
    max_variants: int = 6,
    conversation: Sequence[object] = (),
) -> list[str]:
    q = str(query or "").strip()
    if not q:
        return []

    rewrites = _rule_rewrites(query)
    if enable_decompose:
        rewrites.extend(_decompose_query(query))
    if enable_llm:
        # The conversation is what turns this from "reword the query" into
        # "complete the follow-up". Without it the rewriter could restate
        # "它的成本呢" more tersely but could never supply what "它" is.
        llm_q = _llm_rewrite(query, conversation, use_reasoning=use_reasoning)
        if llm_q:
            rewrites.append(llm_q)

    # Dedupe while preserving order
    # Use normalized form for comparison but keep original form
    seen: set[str] = set()
    out: list[str] = []

    for item in rewrites:
        original = item.strip()
        if not original:
            continue

        # Normalize for comparison: lowercase + collapse whitespace
        normalized = re.sub(r"\s+", " ", original.lower())

        if normalized in seen:
            continue

        seen.add(normalized)
        out.append(original)

        if len(out) >= max_variants:
            break

    return out
