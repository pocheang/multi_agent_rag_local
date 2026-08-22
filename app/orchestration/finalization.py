"""Shared grounding, safety, validation, and quality finalization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.contracts import EvidenceBundle, FinalAnswer, OrchestratedQualityReport, ValidationStatus
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest

Validator = Callable[[str, str, list[dict[str, Any]], list[dict[str, Any]]], Awaitable[Any]]


class FinalizationService:
    """The only terminal-answer policy boundary for every Engine execution."""

    def __init__(self, validator: Validator | None = None) -> None:
        self._validator = validator or _validate

    async def finalize(
        self,
        request: OrchestrationRequest,
        evidence: EvidenceBundle,
        candidate: FinalAnswer,
        policy: ExecutionPolicy,
    ) -> FinalAnswer:
        grounded, grounding = _ground(candidate.answer, evidence)
        safe, safety = _sanitize(grounded)
        validation = await self._validation_status(request, safe, evidence)
        quality = _quality_report(validation, grounding, policy)

        return candidate.model_copy(
            update={
                "answer": safe,
                "citations": candidate.citations or evidence.citations,
                "evidence": evidence,
                "evidence_ids": candidate.evidence_ids or evidence.item_ids,
                "grounding": grounding,
                "safety": safety,
                "validation": validation,
                "quality_report": quality,
                "execution_metadata": {
                    **(candidate.execution_metadata or {}),
                    "profile": policy.profile.value,
                    "validation_required": policy.require_answer_validation,
                },
            }
        )

    async def _validation_status(
        self,
        request: OrchestrationRequest,
        answer: str,
        evidence: EvidenceBundle,
    ) -> ValidationStatus:
        documents = [
            {"content": item.content, "source": item.source, "document_id": item.document_id, "page": item.page}
            for item in evidence.items
        ]
        citations = [
            {"document_id": item.document_id, "source": item.source, "page": item.page} for item in evidence.items
        ]
        try:
            result = await self._validator(request.question, answer, documents, citations)
        except Exception as exc:
            return ValidationStatus(
                state="degraded",
                approved=False,
                method="exception",
                issues=(f"validation exception: {type(exc).__name__}",),
            )

        # Extract validation result with clear error messages
        try:
            is_valid = bool(result.is_valid) if hasattr(result, "is_valid") else False
            action = str(result.action) if hasattr(result, "action") else ""
            approved = is_valid and action == "approve"

            raw_issues = result.issues if hasattr(result, "issues") else ()
            # Safely convert issues to strings, handling various types
            issues = []
            for issue in raw_issues or ():
                try:
                    if hasattr(issue, "content"):
                        issues.append(str(issue.content))
                    elif isinstance(issue, str):
                        issues.append(issue)
                    else:
                        issues.append(str(issue))
                except Exception:
                    issues.append("[issue conversion failed]")

            method = str(result.validation_method) if hasattr(result, "validation_method") else "cascade"
        except (AttributeError, ValueError, TypeError) as exc:
            return ValidationStatus(
                state="degraded",
                approved=False,
                method="extraction_error",
                issues=(f"Failed to extract validation result: {exc}",),
            )

        return ValidationStatus(
            state="validated" if approved else "rejected",
            approved=approved,
            method=method,
            issues=tuple(issues),
        )


async def _validate(query: str, answer: str, documents: list[dict[str, Any]], citations: list[dict[str, Any]]) -> Any:
    from app.agents.validation.public import validate_answer

    return await validate_answer(query, answer, documents, citations)


def _ground(answer: str, evidence: EvidenceBundle) -> tuple[str, dict[str, Any]]:
    from app.services.retrieval.citation_grounding import apply_sentence_grounding

    return apply_sentence_grounding(answer, [item.content for item in evidence.items])


def _sanitize(answer: str) -> tuple[str, dict[str, Any]]:
    from app.services.answer_safety import sanitize_answer

    return sanitize_answer(answer)


def _quality_report(
    validation: ValidationStatus,
    grounding: dict[str, Any],
    policy: ExecutionPolicy,
) -> OrchestratedQualityReport | None:
    if not policy.require_quality_report:
        return None
    support = float(grounding.get("support_ratio", 0.0) or 0.0)
    score = support if validation.approved else 0.0
    return OrchestratedQualityReport(
        score=score,
        level="high" if score >= 0.8 else "low",
        details={"validation_state": validation.state, "grounding_support_ratio": support},
    )
