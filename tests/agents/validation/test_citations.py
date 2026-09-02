"""Regression tests for CitationValidator's inline-marker detection."""

from __future__ import annotations

import pytest

from app.agents.validation.citations import CitationValidator
from app.agents.validation.models import ValidationRequest


@pytest.mark.asyncio
async def test_evidence_marker_citation_suppresses_missing_citation_issue():
    """An answer that already cites [E1] must not be flagged as uncited,
    even when no structured ValidationCitation objects were supplied."""
    request = ValidationRequest.from_compatibility(
        query="What was the reported revenue?",
        answer="Revenue grew to 42 million dollars [E1].",
        source_docs=[{"id": "doc1", "content": "Revenue grew to 42 million dollars in Q4."}],
        citations=[],
    )

    result = await CitationValidator().validate(request)

    issue_types = [issue.issue_type for issue in result.issues]
    assert "missing_citation" not in issue_types


@pytest.mark.asyncio
async def test_factual_answer_without_any_marker_is_still_flagged():
    """An answer with a factual claim and no citation marker at all must
    still be flagged — the fix must not disable this check entirely."""
    request = ValidationRequest.from_compatibility(
        query="What was the reported revenue?",
        answer="Revenue grew to 42 million dollars.",
        source_docs=[{"id": "doc1", "content": "Revenue grew to 42 million dollars in Q4."}],
        citations=[],
    )

    result = await CitationValidator().validate(request)

    issue_types = [issue.issue_type for issue in result.issues]
    assert "missing_citation" in issue_types
