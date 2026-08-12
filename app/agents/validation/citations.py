"""Citation completeness and source cross-checking."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.validation.models import (
    CascadeLevel,
    CascadeResult,
    RuleBasisIssue,
    SourceDocument,
    ValidationCitation,
    ValidationRequest,
)
from app.agents.validation.rules import extract_dates, extract_numbers, numbers_match


def citation_completeness(
    _answer: str,
    citations: Sequence[Mapping[str, Any] | ValidationCitation],
    source_docs: Sequence[Mapping[str, Any] | SourceDocument],
) -> float:
    """Return the fraction of citations that reference supplied evidence."""
    normalized_citations = tuple(ValidationCitation.from_value(item) for item in citations)
    if not normalized_citations:
        return 0.0
    source_ids = {SourceDocument.from_value(item).identifier for item in source_docs}
    valid = sum(citation.doc_id in source_ids for citation in normalized_citations)
    return valid / len(normalized_citations)


class CitationValidator:
    """Validate citation presence, identity, and cited numeric evidence."""

    async def validate(self, request: ValidationRequest) -> CascadeResult:
        start_time = time.time()
        issues: list[RuleBasisIssue] = []
        if not request.citations:
            factual = bool(extract_numbers(request.answer) or extract_dates(request.answer))
            has_inline_marker = bool(re.findall(r"\[(\d+)\]", request.answer))
            if factual and not has_inline_marker:
                issues.append(
                    RuleBasisIssue(
                        issue_type="missing_citation",
                        severity="medium",
                        content="Factual claims without citations",
                        suggestion="Add citations for key claims",
                    )
                )

        sources_by_id = {doc.identifier: doc for doc in request.source_docs}
        for citation in request.citations:
            source_doc = sources_by_id.get(citation.doc_id)
            if source_doc is None:
                issues.append(
                    RuleBasisIssue(
                        issue_type="citation_invalid",
                        severity="high",
                        content=f"Citation {citation.doc_id} not found in sources",
                        suggestion="Verify citation references",
                    )
                )
                continue
            for cited_number in extract_numbers(citation.content):
                if not any(numbers_match(cited_number, value) for value in extract_numbers(source_doc.content)):
                    issues.append(
                        RuleBasisIssue(
                            issue_type="citation_mismatch",
                            severity="high",
                            content=f"Citation number {cited_number} not in source",
                            suggestion="Verify cited values",
                        )
                    )
                    break

        confidence = max(0.0, 1.0 - len(issues) * 0.15)
        return CascadeResult(
            level=CascadeLevel.CITATION_CHECK,
            has_issues=bool(issues),
            confidence_score=confidence,
            issues=issues,
            execution_time_ms=int((time.time() - start_time) * 1_000),
            should_continue=True,
        )


__all__ = ["CitationValidator", "citation_completeness"]
