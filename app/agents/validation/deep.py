"""Deep LLM validation for low-confidence answers."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.validation.models import CascadeLevel, CascadeResult, RuleBasisIssue, ValidationRequest
from app.services.models.runtime import get_chat_model

logger = logging.getLogger(__name__)


class DeepValidator:
    """Use one bounded LLM check after deterministic stages flag risk."""

    def __init__(self, *, timeout_ms: int = 3_000) -> None:
        self.timeout_ms = timeout_ms

    async def validate(self, request: ValidationRequest) -> CascadeResult:
        start_time = time.time()
        source_text = "\n".join(doc.content[:500] for doc in request.source_docs[:3])
        if not source_text:
            return _result(start_time, confidence=0.5)
        try:
            response = await asyncio.wait_for(
                get_chat_model(temperature=0.0).ainvoke(_prompt(request, source_text)),
                timeout=self.timeout_ms / 1_000,
            )
            content = response.content if hasattr(response, "content") else str(response)
            is_factual, confidence, issues = _parse_response(str(content))
            return _result(
                start_time,
                confidence=confidence if is_factual else confidence * 0.5,
                issues=issues,
            )
        except TimeoutError:
            logger.warning("Deep validation timed out after %sms", self.timeout_ms)
        except Exception as exc:
            logger.warning("Deep validation failed: %s", exc)
        return _result(start_time, confidence=0.6)


def _prompt(request: ValidationRequest, source_text: str) -> str:
    return f"""Verify if this answer is factually consistent with the source documents.
Check for direct contradictions, unsupported claims, overgeneralizations, and implied facts.

Query: {request.query}

Answer: {request.answer}

Source Documents:
{source_text}

Respond in this format:
FACTUAL: yes/no
CONFIDENCE: 0.0-1.0
ISSUES: list any problems (or "none")
"""


def _parse_response(content: str) -> tuple[bool, float, list[RuleBasisIssue]]:
    lowered = content.lower()
    is_factual = True
    if "factual:" in lowered:
        is_factual = "yes" in lowered.split("factual:", 1)[1].split("\n", 1)[0]
    confidence = 0.7
    match = re.search(r"confidence:\s*([\d.]+)", lowered)
    if match:
        confidence = max(0.0, min(1.0, float(match.group(1))))
    if is_factual:
        return True, confidence, []
    issue_text = "Factual inconsistency detected"
    if "issues:" in lowered:
        candidate = lowered.split("issues:", 1)[1].split("\n", 1)[0].strip()
        if candidate and "none" not in candidate:
            issue_text = candidate
    issue = RuleBasisIssue(
        issue_type="llm_hallucination",
        severity="high",
        content=issue_text,
        suggestion="Review answer against sources",
    )
    return False, confidence, [issue]


def _result(
    start_time: float,
    *,
    confidence: float,
    issues: list[RuleBasisIssue] | None = None,
) -> CascadeResult:
    stage_issues = issues or []
    return CascadeResult(
        level=CascadeLevel.DEEP_LLM,
        has_issues=bool(stage_issues),
        confidence_score=max(0.0, min(1.0, confidence)),
        issues=stage_issues,
        execution_time_ms=int((time.time() - start_time) * 1_000),
        should_continue=True,
    )


async def deep_validation_score(
    query: str,
    answer: str,
    source_docs: Sequence[Mapping[str, Any]],
) -> float:
    """Retain the historical score-only helper for test/import compatibility."""
    request = ValidationRequest.from_compatibility(
        query=query,
        answer=answer,
        source_docs=source_docs,
        citations=(),
    )
    return (await DeepValidator(timeout_ms=1_000).validate(request)).confidence_score


__all__ = ["DeepValidator", "deep_validation_score"]
