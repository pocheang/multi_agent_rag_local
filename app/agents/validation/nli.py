"""Natural-language-inference validation and compatibility helpers."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.shared.config import NLI_MAX_CHECKS, NLI_MODEL_NAME
from app.agents.validation.models import CascadeLevel, CascadeResult, RuleBasisIssue, ValidationRequest
from app.agents.validation.rules import extract_dates, extract_numbers, numbers_match

logger = logging.getLogger(__name__)


class NLIValidator:
    """Validate answer sentences against normalized source evidence."""

    def __init__(self, *, model_name: str = NLI_MODEL_NAME, max_checks: int = NLI_MAX_CHECKS) -> None:
        self.model_name = model_name
        self.max_checks = max_checks
        self._model: Any | None = None
        self._load_attempted = False

    def get_model(self) -> Any | None:
        """Lazily load the optional cross-encoder."""
        if self._load_attempted:
            return self._model
        self._load_attempted = True
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            logger.info("Loaded validation NLI model: %s", self.model_name)
        except ImportError:
            logger.warning("sentence-transformers is not available for NLI validation")
        except Exception as exc:
            logger.warning("Failed to load validation NLI model: %s", exc)
        return self._model

    def extract_factual_spans(self, answer: str) -> list[str]:
        """Extract bounded high-risk spans for compatibility callers."""
        spans: list[str] = []
        spans.extend(re.findall(r"\d+\.?\d*%?", answer))
        spans.extend(re.findall(r"\d{4}[年\-/]\d{1,2}[月\-/]?\d{0,2}日?", answer))
        spans.extend(re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", answer))
        spans.extend(re.findall(r"[一-鿿]{2,}", answer))
        spans.extend(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", answer))
        return list(dict.fromkeys(spans))[: self.max_checks]

    async def check_hallucination(
        self,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
    ) -> float:
        """Return the historical factual-span score."""
        spans = self.extract_factual_spans(answer)
        source_text = " ".join(
            str(doc.get("content", doc.get("text", "")) or "") for doc in source_docs[:5]
        )
        if not spans or not source_text:
            return 0.5
        model = self.get_model()
        if model is None:
            return 0.7
        try:
            import numpy as np

            unsupported = 0
            for span in spans:
                if len(span) < 2:
                    continue
                scores = model.predict([(source_text, f"The document mentions: {span}")])
                entailment = float(scores[0, 2]) if isinstance(scores, np.ndarray) and scores.ndim > 1 else 0.0
                if entailment < 0.5:
                    unsupported += 1
            return 1.0 - unsupported / len(spans)
        except Exception as exc:
            logger.warning("NLI factual-span check failed: %s", exc)
            return 0.7

    async def validate(self, request: ValidationRequest) -> CascadeResult:
        """Run sentence-level batch NLI with a deterministic local fallback."""
        start_time = time.time()
        sentences = [
            sentence.strip()
            for sentence in re.split(r"[。！？.!?]\s*", request.answer)
            if sentence.strip() and len(sentence.strip()) > 10
        ]
        if not sentences:
            return _result(start_time, confidence=1.0)
        source_text = " ".join(doc.content for doc in request.source_docs[:5])
        if not source_text:
            return _result(start_time, confidence=0.5)

        model = self.get_model()
        if model is None:
            return self._fallback(sentences, source_text, start_time)
        try:
            import numpy as np

            scores = model.predict([(source_text, sentence) for sentence in sentences])
            nli_scores: list[float] = []
            unsupported: list[str] = []
            for index, sentence in enumerate(sentences):
                if isinstance(scores, np.ndarray):
                    entailment = float(scores[index, 2]) if scores.ndim > 1 else float(scores[2])
                else:
                    entailment = 0.5
                entailment = max(0.0, min(1.0, entailment))
                nli_scores.append(entailment)
                if entailment < 0.5:
                    unsupported.append(sentence[:50])
            issues = _unsupported_issue(len(unsupported), len(sentences), "not entailed")
            confidence = sum(nli_scores) / len(nli_scores) if nli_scores else 0.5
            return _result(start_time, confidence=confidence, issues=issues, scores=nli_scores)
        except Exception as exc:
            logger.warning("NLI batch validation failed: %s", exc)
            return _result(start_time, confidence=0.7)

    def _fallback(self, sentences: list[str], source_text: str, start_time: float) -> CascadeResult:
        source_numbers = extract_numbers(source_text)
        source_dates = extract_dates(source_text)
        source_words = set(re.findall(r"\w+", source_text.lower()))
        unsupported = 0
        for sentence in sentences:
            sentence_numbers = extract_numbers(sentence)
            numbers_supported = all(
                any(numbers_match(number, source) for source in source_numbers)
                for number in sentence_numbers
            ) if sentence_numbers else True
            sentence_dates = extract_dates(sentence)
            dates_supported = all(date in source_dates for date in sentence_dates) if sentence_dates else True
            words = set(re.findall(r"\w+", sentence.lower()))
            overlap = len(words & source_words) / len(words) if words else 0.0
            if not numbers_supported or not dates_supported or overlap < 0.25:
                unsupported += 1
        confidence = 1.0 - unsupported / len(sentences)
        issues = _unsupported_issue(unsupported, len(sentences), "not supported by sources")
        return _result(start_time, confidence=confidence, issues=issues)


def _unsupported_issue(count: int, total: int, label: str) -> list[RuleBasisIssue]:
    if count <= total * 0.3:
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
    )


_compatibility_validator = NLIValidator()


def get_nli_model() -> Any | None:
    return _compatibility_validator.get_model()


def extract_factual_spans(answer: str) -> list[str]:
    return _compatibility_validator.extract_factual_spans(answer)


async def check_hallucination(answer: str, source_docs: Sequence[Mapping[str, Any]]) -> float:
    return await _compatibility_validator.check_hallucination(answer, source_docs)


__all__ = ["NLIValidator", "check_hallucination", "extract_factual_spans", "get_nli_model"]
