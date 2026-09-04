"""Sentence-level entailment checking for the validation cascade.

This stage never ran. `CASCADE_ENABLE_LEVEL2` gates it -- `CascadeLevel.NLI_BATCH`
is level 2 -- and defaulted to False, while CLAUDE.md listed NLI among the checks
answer validation performs. Turning it on would have been worse than leaving it
off, for three independent reasons, all fixed here:

* **It blocked the event loop.** `model.predict(...)` -- a synchronous
  cross-encoder forward pass -- was called directly inside `async def`, with no
  `asyncio.to_thread`, no timeout and no circuit breaker. `get_model()` loaded the
  model on the loop too, and without `local_files_only=True`, so a machine that
  had never downloaded it would have started an untimed network download inside a
  request.

* **The deterministic fallback could not score Chinese.** It tokenised with
  `re.findall(r"\\w+", ...)`, and `\\w` matches CJK, so a whole Chinese clause
  became *one* token. Measured on realistic pairs: a verbatim clause copy scored
  1.00, but a paraphrase, a recombination of two sources, and a sentence with an
  added connective all scored **0.00**. Synthesis paraphrases and recombines by
  construction, so three of four realistic shapes were counted unsupported --
  which the verifier turns into `factuality < 0.7` and then a rejected answer.

* **The model is English.** `NLI_MODEL_NAME` defaults to an English
  cross-encoder, and the code reads `scores[:, 2]` as its entailment column,
  which is model-specific. On Chinese pairs its output is noise, so the
  cross-encoder now runs only on predominantly-Latin text and everything else
  takes the (repaired) deterministic path. Which one ran is reported rather than
  assumed -- see `CascadeResult.backend`.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from functools import lru_cache
from typing import Any

from app.agents.validation.models import CascadeLevel, CascadeResult, RuleBasisIssue, ValidationRequest
from app.agents.validation.rules import extract_dates, extract_numbers, numbers_match
from app.core.config import get_settings
from app.services.runtime.resilience import call_with_circuit_breaker

logger = logging.getLogger(__name__)

# The repository's existing CJK-aware tokenizer shape, not a fourth one. Latin
# runs stay whole; each CJK character is its own token, which is what gives
# partial credit for a paraphrase instead of all-or-nothing on the whole clause.
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[一-鿿]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")
_CJK_PATTERN = re.compile(r"[一-鿿]")

# Below this share of overlapping tokens a sentence counts as unsupported.
_SUPPORT_THRESHOLD = 0.25
# Above this share of unsupported sentences the stage raises an issue.
_UNSUPPORTED_SHARE = 0.3


def tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall((text or "").lower()))


def is_predominantly_latin(text: str) -> bool:
    """Whether the English cross-encoder can say anything useful about this text."""

    latin = len(_LATIN_PATTERN.findall(text or ""))
    cjk = len(_CJK_PATTERN.findall(text or ""))
    return latin > cjk


@lru_cache(maxsize=1)
def load_nli_cross_encoder() -> Any | None:
    """Process-wide lazy loader, shaped exactly like `_load_cross_encoder`.

    `local_files_only=True` is the load-bearing part: it turns "the model was
    never downloaded" from an untimed network fetch inside a request into an
    instant `None`, and the caller already has a deterministic path for `None`.

    Every failure returns `None` rather than raising, for the same reason the
    reranker does: validation degrading is acceptable, validation taking the
    request down with it is not.
    """

    model_name = get_settings().nli_model_name
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name, local_files_only=True)
        logger.info("Loaded validation NLI model: %s", model_name)
        return model
    except ImportError:
        logger.warning("sentence-transformers is not available for NLI validation")
    except (OSError, ValueError) as exc:
        logger.warning(
            "Validation NLI model %s is not available locally (%s); "
            "download it or leave CASCADE_ENABLE_NLI on with the deterministic path.",
            model_name,
            exc,
        )
    except RuntimeError as exc:
        logger.warning("Failed to load validation NLI model: %s", exc)
    return None


class NLIValidator:
    """Validate answer sentences against normalized source evidence."""

    def __init__(self, *, model_name: str | None = None, max_sentences: int | None = None) -> None:
        settings = get_settings()
        # Kept for tests that want to pin a name; the shared loader owns the real
        # one so the model is loaded once per process rather than per cascade.
        self.model_name = settings.nli_model_name if model_name is None else model_name
        # Bounds the batch handed to `model.predict`. An unbounded batch is what
        # makes any timeout on this stage unpredictable.
        self.max_sentences = settings.nli_max_sentences if max_sentences is None else max_sentences
        self.timeout_ms = settings.cascade_nli_timeout_ms

    def get_model(self) -> Any | None:
        return load_nli_cross_encoder()

    async def validate(self, request: ValidationRequest) -> CascadeResult:
        """Score sentences off the event loop, and say which scorer ran."""

        start_time = time.time()
        sentences = [
            sentence.strip()
            for sentence in re.split(r"[。！？.!?]\s*", request.answer)
            if sentence.strip() and len(sentence.strip()) > 10
        ][: max(1, self.max_sentences)]
        if not sentences:
            return _result(start_time, confidence=1.0, backend="none", fallback_reason="no_sentences")
        source_text = " ".join(doc.content for doc in request.source_docs[:5])
        if not source_text:
            return _result(start_time, confidence=0.5, backend="none", fallback_reason="no_sources")

        model = self.get_model() if is_predominantly_latin(request.answer) else None
        if model is None:
            reason = "model_unavailable" if is_predominantly_latin(request.answer) else "non_latin_text"
            return _lexical(sentences, source_text, start_time, reason)

        try:
            scores = await asyncio.wait_for(
                asyncio.to_thread(_score_sentences, model, source_text, sentences),
                timeout=max(0.05, self.timeout_ms / 1000),
            )
        except TimeoutError:
            return _lexical(sentences, source_text, start_time, "timeout")
        except Exception as exc:
            logger.warning("NLI batch validation failed: %s", type(exc).__name__)
            return _lexical(sentences, source_text, start_time, type(exc).__name__)

        unsupported = [sentence for sentence, score in zip(sentences, scores, strict=True) if score < 0.5]
        return _result(
            start_time,
            confidence=sum(scores) / len(scores) if scores else 0.5,
            issues=_unsupported_issue(len(unsupported), len(sentences), "not entailed"),
            scores=scores,
            backend="cross_encoder",
        )


def entailment_index(model: Any) -> int:
    """Which output column means "entailed", according to the model itself.

    The old code hardcoded column 2. For the configured default
    (`cross-encoder/nli-MiniLM2-L6-H768`) `id2label` is
    `{0: contradiction, 1: entailment, 2: neutral}` -- so it read *neutral* as
    entailment, and the scoring came out inverted. Measured against that model:

        sentence        old (col 2, clamped)    correct (softmax col 1)
        entailed                       0.000                      0.993
        contradiction                  0.000                      0.001
        unrelated                      0.894                      0.000

    An entailed sentence scored zero and an unrelated one scored highest, so
    enabling this stage as it stood would have marked essentially every grounded
    English answer unsupported -- and the verifier turns that into a rejected
    answer. Asking the model which column is which is the only version of this
    that survives someone setting `NLI_MODEL_NAME` to a different checkpoint.
    """

    labels = getattr(getattr(model, "model", None), "config", None)
    mapping = getattr(labels, "id2label", None) or {}
    for index, name in mapping.items():
        if str(name).strip().lower() == "entailment":
            return int(index)
    # No usable mapping: 1 is the conventional position in three-way NLI heads
    # (contradiction, entailment, neutral).
    return 1


def _softmax(row: Any) -> Any:
    import numpy as np

    shifted = np.asarray(row, dtype=float) - float(np.max(row))
    exponentiated = np.exp(shifted)
    return exponentiated / exponentiated.sum()


def _score_sentences(model: Any, source_text: str, sentences: list[str]) -> list[float]:
    """The synchronous core. Knows nothing about asyncio, by design.

    Same shape as `rerank_with_diagnostics`: the blocking call is wrapped in the
    process-wide breaker, and the async layer above owns the thread hop and the
    timeout.

    `model.predict` returns raw logits, not probabilities. The old code clamped
    them into [0, 1], which made nearly every score exactly 0.0 or 1.0; softmax
    over the row is what turns them into the entailment probability the caller's
    0.5 threshold assumes.
    """

    import numpy as np

    raw = call_with_circuit_breaker(
        "validation.nli.predict",
        lambda: model.predict([(source_text, sentence) for sentence in sentences]),
    )
    if not isinstance(raw, np.ndarray) or raw.ndim < 2:
        return [0.5] * len(sentences)
    column = min(entailment_index(model), raw.shape[1] - 1)
    return [float(_softmax(raw[index])[column]) for index in range(len(sentences))]


def _lexical(sentences: list[str], source_text: str, start_time: float, reason: str) -> CascadeResult:
    """Deterministic support scoring by token overlap, numbers and dates.

    The tokenizer is the whole story here. With `re.findall(r"\\w+", ...)` an
    entire Chinese clause was one token, so only a verbatim copy of a source
    clause could match and every paraphrase scored 0.00.
    """

    source_numbers = extract_numbers(source_text)
    source_dates = extract_dates(source_text)
    source_tokens = tokenize(source_text)
    unsupported = 0
    for sentence in sentences:
        sentence_numbers = extract_numbers(sentence)
        numbers_supported = (
            all(any(numbers_match(number, source) for source in source_numbers) for number in sentence_numbers)
            if sentence_numbers
            else True
        )
        sentence_dates = extract_dates(sentence)
        dates_supported = all(date in source_dates for date in sentence_dates) if sentence_dates else True
        tokens = tokenize(sentence)
        overlap = len(tokens & source_tokens) / len(tokens) if tokens else 0.0
        if not numbers_supported or not dates_supported or overlap < _SUPPORT_THRESHOLD:
            unsupported += 1
    return _result(
        start_time,
        confidence=1.0 - unsupported / len(sentences),
        issues=_unsupported_issue(unsupported, len(sentences), "not supported by sources"),
        backend="lexical",
        fallback_reason=reason,
    )


def _unsupported_issue(count: int, total: int, label: str) -> list[RuleBasisIssue]:
    if count <= total * _UNSUPPORTED_SHARE:
        return []
    return [
        RuleBasisIssue(
            issue_type="nli_contradiction",
            severity="high",
            content=f"{count} sentences {label}",
            suggestion="Verify claims against sources",
        )
    ]


def _result(
    start_time: float,
    *,
    confidence: float,
    issues: list[RuleBasisIssue] | None = None,
    scores: list[float] | None = None,
    backend: str = "",
    fallback_reason: str | None = None,
) -> CascadeResult:
    stage_issues = issues or []
    return CascadeResult(
        level=CascadeLevel.NLI_BATCH,
        has_issues=bool(stage_issues),
        confidence_score=max(0.0, min(1.0, confidence)),
        issues=stage_issues,
        execution_time_ms=int((time.time() - start_time) * 1_000),
        nli_scores=scores,
        should_continue=True,
        backend=backend,
        fallback_reason=fallback_reason,
    )


__all__ = [
    "NLIValidator",
    "entailment_index",
    "is_predominantly_latin",
    "load_nli_cross_encoder",
    "tokenize",
]
