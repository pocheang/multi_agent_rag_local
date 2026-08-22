"""Single production orchestration entry for answer validation."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.validation.citations import CitationValidator, citation_completeness
from app.agents.validation.deep import DeepValidator
from app.agents.validation.fact_verification import (
    AnswerVerificationResult,
    FactVerificationStage,
)
from app.agents.validation.models import (
    CascadeLevel,
    CascadeResult,
    RuleBasisIssue,
    ValidationCascadeResult,
    ValidationRequest,
)
from app.agents.validation.nli import NLIValidator
from app.agents.validation.rules import RuleValidator, assess_answer_quality, quick_validation, safety_score


class ValidationCascade:
    """Run one ordered rule, citation, NLI, and deep-validation pipeline."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = dict(config or {})
        self.level1_timeout_ms = int(self.config.get("level1_timeout_ms", 10))
        self.level2_timeout_ms = int(self.config.get("level2_timeout_ms", 3_000))
        self.level3_timeout_ms = int(self.config.get("level3_timeout_ms", 75))
        self.level4_timeout_ms = int(self.config.get("level4_timeout_ms", 3_000))
        self.enable_level1 = bool(self.config.get("enable_level1", True))
        self.enable_level2 = bool(self.config.get("enable_level2", False))
        self.enable_level3 = bool(self.config.get("enable_level3", True))
        self.enable_level4 = bool(self.config.get("enable_level4", True))
        self.enforce_minimum_length = bool(self.config.get("enforce_minimum_length", False))
        self.rule_validator = RuleValidator()
        self.citation_validator = CitationValidator()
        self.nli_validator = NLIValidator()
        self.deep_validator = DeepValidator(timeout_ms=self.level4_timeout_ms)
        self.fact_verification_stage = FactVerificationStage()

    async def validate(
        self,
        query: str,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
        citations: Sequence[Mapping[str, Any]],
    ) -> ValidationCascadeResult:
        """Validate one answer through the only production cascade entry."""
        started = time.time()
        request = ValidationRequest.from_compatibility(
            query=query,
            answer=answer,
            source_docs=source_docs,
            citations=citations,
        )
        quality = assess_answer_quality(request.answer)
        citation_score = citation_completeness(request.answer, request.citations, request.source_docs)
        quick = quick_validation(request.answer, request.citations)
        enforce_quick_rejection = quick["reason"] == "safety_issue" or self.enforce_minimum_length
        if quick["reject"] and enforce_quick_rejection:
            safety = 0.0 if quick["reason"] == "safety_issue" else 1.0
            issue_type = (
                f"pii_{quick.get('pattern_type', 'unknown')}"
                if quick["reason"] == "safety_issue"
                else "answer_too_short"
            )
            issue = RuleBasisIssue(
                issue_type=issue_type,
                severity="critical",
                content=request.answer[:100],
                suggestion=str(quick["reason"]),
            )
            stage = CascadeResult(
                level=CascadeLevel.RULE_BASED,
                has_issues=True,
                confidence_score=0.0,
                issues=[issue],
                execution_time_ms=_elapsed(started),
                should_continue=False,
            )
            return _finish(
                started,
                [stage],
                citation_score=citation_score,
                quality=quality,
                safety=safety,
            )

        results: list[CascadeResult] = []
        if self.enable_level1:
            rules = await self.rule_validator.validate(request)
            results.append(rules)
            if not rules.should_continue:
                return _finish(
                    started,
                    results,
                    citation_score=citation_score,
                    quality=quality,
                    safety=0.0,
                )

        last_confidence = results[-1].confidence_score if results else 1.0
        if self.enable_level3 and last_confidence >= 0.5:
            results.append(await self.citation_validator.validate(request))

        last_confidence = results[-1].confidence_score if results else 1.0
        if self.enable_level2 and last_confidence >= 0.5:
            results.append(await self.nli_validator.validate(request))

        all_issues = [issue for result in results for issue in result.issues]
        non_citation_risk = any(
            result.level != CascadeLevel.CITATION_CHECK and result.confidence_score < 0.7 for result in results
        )
        should_run_deep = self.enable_level4 and bool(all_issues) and (quality < 0.6 or non_citation_risk)
        if should_run_deep:
            results.append(await self.deep_validator.validate(request))

        return _finish(
            started,
            results,
            citation_score=citation_score,
            quality=quality,
            safety=safety_score(request.answer),
        )

    async def run_fact_verification_stage(
        self,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
        citations: Sequence[Mapping[str, Any]] | None = None,
    ) -> AnswerVerificationResult:
        """Run the cascade-owned claim-groundedness stage.

        Synthesis uses this focused stage to preserve its historical result
        metadata without creating a second answer-validation engine.  The
        fact-verification implementation intentionally ignores explicit
        citations today, matching the previous ``FactVerifier`` contract.
        """
        return await self.fact_verification_stage.verify(
            answer,
            list(source_docs),
            list(citations) if citations is not None else None,
        )

    async def run_cascade(
        self,
        query: str,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
        citations: Sequence[Mapping[str, Any]],
    ) -> ValidationCascadeResult:
        """Compatibility alias; all execution enters :meth:`validate`."""
        return await self.validate(query, answer, source_docs, citations)

    async def validate_level1(
        self,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
    ) -> CascadeResult:
        """Compatibility adapter for focused rule-stage tests."""
        return await self.rule_validator.validate(_request(answer=answer, source_docs=source_docs))

    async def validate_level2(
        self,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
    ) -> CascadeResult:
        """Compatibility adapter for focused NLI-stage tests."""
        return await self.nli_validator.validate(_request(answer=answer, source_docs=source_docs))

    async def validate_level3(
        self,
        answer: str,
        citations: Sequence[Mapping[str, Any]],
        source_docs: Sequence[Mapping[str, Any]],
    ) -> CascadeResult:
        """Compatibility adapter for focused citation-stage tests."""
        return await self.citation_validator.validate(
            _request(answer=answer, source_docs=source_docs, citations=citations)
        )

    async def validate_level4(
        self,
        query: str,
        answer: str,
        source_docs: Sequence[Mapping[str, Any]],
    ) -> CascadeResult:
        """Compatibility adapter for focused deep-stage tests."""
        return await self.deep_validator.validate(_request(query=query, answer=answer, source_docs=source_docs))

    def _get_nli_model(self) -> Any | None:
        """Compatibility adapter for the former cascade-local model loader."""
        return self.nli_validator.get_model()


def _request(
    *,
    answer: str,
    source_docs: Sequence[Mapping[str, Any]],
    query: str = "",
    citations: Sequence[Mapping[str, Any]] = (),
) -> ValidationRequest:
    return ValidationRequest.from_compatibility(
        query=query,
        answer=answer,
        source_docs=source_docs,
        citations=citations,
    )


def _finish(
    started: float,
    results: list[CascadeResult],
    *,
    citation_score: float,
    quality: float,
    safety: float,
) -> ValidationCascadeResult:
    issues = [issue for result in results for issue in result.issues]
    confidence = _weighted_confidence(results)
    highest = results[-1].level if results else CascadeLevel.RULE_BASED
    elapsed = _elapsed(started)
    return ValidationCascadeResult(
        has_issues=bool(issues),
        confidence_score=round(confidence, 3),
        highest_level_reached=highest,
        all_issues=issues,
        total_execution_time_ms=elapsed,
        execution_time_ms=elapsed,
        level_results=results,
        citation_completeness=citation_score,
        answer_quality=quality,
        safety_score=safety,
    )


def _weighted_confidence(results: list[CascadeResult]) -> float:
    if not results:
        return 0.5
    weights = (0.2, 0.3, 0.3, 0.2)
    used_weights = weights[: len(results)]
    weighted = sum(result.confidence_score * weight for result, weight in zip(results, used_weights, strict=True))
    return weighted / sum(used_weights)


def _elapsed(started: float) -> int:
    return int((time.time() - started) * 1_000)


__all__ = ["ValidationCascade"]
