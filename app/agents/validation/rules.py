"""Deterministic answer-safety and hallucination rules."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.validation.hallucination_patterns import detect_all_patterns
from app.agents.validation.models import (
    CascadeLevel,
    CascadeResult,
    RuleBasisIssue,
    ValidationCascadeResult,
    ValidationRequest,
)


def extract_numbers(text: str) -> list[float]:
    """Extract normalized numeric values from English and Chinese text."""
    pattern = r"\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|M|B|K|thousand))?"
    numbers: list[float] = []
    for match in re.findall(pattern, text, re.IGNORECASE):
        cleaned = re.sub(r"[,$\s]", "", match)
        multiplier = 1.0
        if "billion" in match.lower() or "B" in match:
            multiplier = 1e9
        elif "million" in match.lower() or "M" in match:
            multiplier = 1e6
        elif "thousand" in match.lower() or "K" in match:
            multiplier = 1e3
        try:
            numbers.append(float(re.sub(r"[a-zA-Z]", "", cleaned)) * multiplier)
        except ValueError:
            continue
    return numbers


def extract_dates(text: str) -> list[str]:
    """Extract common year, date, and quarter forms."""
    dates = list(re.findall(r"\b((?:19|20)\d{2})\b", text))
    dates.extend(re.findall(r"\d{4}年(?:\d{1,2}月)?(?:\d{1,2}日)?", text))
    dates.extend(re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", text))
    dates.extend(re.findall(r"\d{4}-\d{2}-\d{2}", text))
    dates.extend(re.findall(r"Q[1-4]\s*\d{4}", text, re.IGNORECASE))
    return dates


def extract_entities(text: str) -> list[str]:
    """Extract lightweight proper-noun candidates."""
    entities = list(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
    entities.extend(re.findall(r"[一-鿿]{2,}", text))
    return entities


def numbers_match(first: float, second: float, tolerance: float = 0.15) -> bool:
    """Return whether two numbers match within a relative tolerance."""
    if first == 0 and second == 0:
        return True
    if first == 0 or second == 0:
        return False
    return abs(first - second) / max(abs(first), abs(second)) <= tolerance


def quick_validation(answer: str, citations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Retain the historical quick-check helper as a compatibility API."""
    unsafe_patterns = (
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (r"\b\d{16}\b", "credit_card"),
        (r"password\s*[:=]\s*\S+", "password"),
    )
    for pattern, pattern_type in unsafe_patterns:
        if re.search(pattern, answer, re.IGNORECASE):
            return {"reject": True, "reason": "safety_issue", "pattern_type": pattern_type}
    if len(answer) < 40:
        return {"reject": True, "reason": "answer_too_short"}
    if not citations:
        return {"reject": False, "reason": "no_citations", "flag": True}
    return {"reject": False, "reason": "passed"}


def assess_answer_quality(answer: str) -> float:
    """Score answer structure and informativeness."""
    quality = 0.8
    if len(answer) < 100:
        quality -= 0.2
    elif len(answer) > 2_000:
        quality -= 0.1
    if len(re.split(r"[。！？.!?]", answer)) < 2:
        quality -= 0.1
    filler_phrases = (
        "不知道",
        "无法回答",
        "没有信息",
        "don't know",
        "cannot answer",
        "no information",
    )
    if any(phrase in answer.lower() for phrase in filler_phrases):
        quality -= 0.3
    return max(0.0, min(1.0, quality))


def safety_score(answer: str) -> float:
    """Return zero for critical sensitive-data patterns, otherwise one."""
    return 0.0 if quick_validation(answer, ())["reason"] == "safety_issue" else 1.0


class RuleValidator:
    """Run the deterministic rule stage."""

    async def validate(self, request: ValidationRequest) -> CascadeResult:
        start_time = time.time()
        issues: list[RuleBasisIssue] = []
        pii_patterns = (
            (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
            (r"\b\d{16}\b", "credit_card"),
            (r"password\s*[:=]\s*\S+", "password"),
            (r"\b[\w.-]+@[\w.-]+\.\w+\b", "email"),
            (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "phone"),
        )
        for pattern, pii_type in pii_patterns:
            if re.search(pattern, request.answer, re.IGNORECASE):
                issues.append(
                    RuleBasisIssue(
                        issue_type=f"pii_{pii_type}",
                        severity="critical",
                        content=f"PII detected: {pii_type}",
                        suggestion="Remove sensitive information",
                    )
                )
        if issues:
            return _result(start_time, issues, confidence=0.0, should_continue=False)

        source_text = " ".join(doc.content for doc in request.source_docs[:5])
        for pattern in detect_all_patterns(request.answer, source_text):
            issues.append(
                RuleBasisIssue(
                    issue_type=pattern.pattern_type,
                    severity=pattern.severity,
                    content=pattern.content,
                    suggestion=pattern.suggestion,
                )
            )
        issue_types = {issue.issue_type for issue in issues}
        if extract_numbers(request.answer) and not extract_numbers(source_text) and "number_mismatch" not in issue_types:
            issues.append(
                RuleBasisIssue(
                    issue_type="number_mismatch",
                    severity="high",
                    content="Numeric claims are absent from source evidence",
                    suggestion="Verify numeric claims against source",
                )
            )
        if extract_dates(request.answer) and not extract_dates(source_text) and "date_mismatch" not in issue_types:
            issues.append(
                RuleBasisIssue(
                    issue_type="date_mismatch",
                    severity="high",
                    content="Date claims are absent from source evidence",
                    suggestion="Verify dates against source documents",
                )
            )
        penalty = sum(0.4 if issue.severity in {"high", "critical"} else 0.2 for issue in issues)
        confidence = max(0.0, 1.0 - penalty)
        return _result(start_time, issues, confidence=confidence, should_continue=True)


def _result(
    start_time: float,
    issues: list[RuleBasisIssue],
    *,
    confidence: float,
    should_continue: bool,
) -> CascadeResult:
    return CascadeResult(
        level=CascadeLevel.RULE_BASED,
        has_issues=bool(issues),
        confidence_score=confidence,
        issues=issues,
        execution_time_ms=int((time.time() - start_time) * 1_000),
        should_continue=should_continue,
    )


# Compatibility exports historically imported from this module.
__all__ = [
    "CascadeLevel",
    "CascadeResult",
    "RuleBasisIssue",
    "RuleValidator",
    "ValidationCascadeResult",
    "assess_answer_quality",
    "extract_dates",
    "extract_entities",
    "extract_numbers",
    "numbers_match",
    "quick_validation",
    "safety_score",
]
