"""Typed contracts shared by answer-validation stages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CascadeLevel(StrEnum):
    """Ordered validation stages exposed by the compatibility API."""

    # Declared in the order they run. `_weighted_confidence` applies its weights
    # positionally, so this and that tuple have to agree -- today's numbers only
    # survived the old (NLI before citation) order because the two middle weights
    # are both 0.3. Do not "fix" that by changing one of them.
    RULE_BASED = "rule_based"
    CITATION_CHECK = "citation_check"
    NLI_BATCH = "nli_batch"
    DEEP_LLM = "deep_llm"


class RuleBasisIssue(BaseModel):
    """One issue found by a validation stage."""

    issue_type: str
    severity: str
    content: str
    suggestion: str | None = None


class CascadeResult(BaseModel):
    """Result from one validation stage."""

    level: CascadeLevel
    has_issues: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    issues: list[RuleBasisIssue] = Field(default_factory=list)
    execution_time_ms: int
    nli_scores: list[float] | None = None
    should_continue: bool = True
    # Which scorer actually ran, and why it was not the preferred one. Without
    # these, `_validation_method` reports "standard" whenever the NLI stage was
    # reached -- including when a lexical heuristic ran because the model was
    # missing or the text was not English. A method name that claims a check
    # happened when it did not is the failure this repository keeps finding.
    backend: str = ""
    fallback_reason: str | None = None


class ValidationCascadeResult(BaseModel):
    """Typed output from the single validation entry."""

    has_issues: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    highest_level_reached: CascadeLevel
    all_issues: list[RuleBasisIssue] = Field(default_factory=list)
    total_execution_time_ms: int
    execution_time_ms: int
    level_results: list[CascadeResult] = Field(default_factory=list)
    citation_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_quality: float = Field(default=0.8, ge=0.0, le=1.0)
    safety_score: float = Field(default=1.0, ge=0.0, le=1.0)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Normalized source evidence consumed inside the validation layer."""

    identifier: str | None
    content: str

    @classmethod
    def from_value(cls, value: SourceDocument | Mapping[str, Any]) -> SourceDocument:
        if isinstance(value, cls):
            return value
        identifier = value.get("id") or value.get("doc_id")
        content = value.get("content", value.get("text", ""))
        return cls(
            identifier=str(identifier) if identifier is not None else None,
            content=str(content or ""),
        )


@dataclass(frozen=True, slots=True)
class ValidationCitation:
    """Normalized citation consumed inside the validation layer."""

    doc_id: str | None
    content: str

    @classmethod
    def from_value(cls, value: ValidationCitation | Mapping[str, Any]) -> ValidationCitation:
        if isinstance(value, cls):
            return value
        doc_id = value.get("doc_id")
        return cls(
            doc_id=str(doc_id) if doc_id is not None else None,
            content=str(value.get("content", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    """Validated data passed between cascade stages."""

    query: str
    answer: str
    source_docs: tuple[SourceDocument, ...]
    citations: tuple[ValidationCitation, ...]

    @classmethod
    def from_compatibility(
        cls,
        *,
        query: str,
        answer: str,
        source_docs: Sequence[SourceDocument | Mapping[str, Any]],
        citations: Sequence[ValidationCitation | Mapping[str, Any]],
    ) -> ValidationRequest:
        return cls(
            query=str(query),
            answer=str(answer),
            source_docs=tuple(SourceDocument.from_value(doc) for doc in source_docs),
            citations=tuple(ValidationCitation.from_value(citation) for citation in citations),
        )


__all__ = [
    "CascadeLevel",
    "CascadeResult",
    "RuleBasisIssue",
    "SourceDocument",
    "ValidationCascadeResult",
    "ValidationCitation",
    "ValidationRequest",
]
