"""Structured privacy results that never expose matched secret values."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.contracts import EvidenceItem


class ImmutablePrivacyContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PrivacyFinding(ImmutablePrivacyContract):
    """Aggregate sensitive-data finding without the original value."""

    kind: str = Field(min_length=1)
    category: Literal["pii", "secret"]
    count: int = Field(ge=1)


class TextPrivacyResult(ImmutablePrivacyContract):
    """Sanitized text and aggregate diagnostics."""

    text: str
    findings: tuple[PrivacyFinding, ...] = Field(default_factory=tuple)
    redaction_count: int = Field(default=0, ge=0)


class SensitiveRegion(ImmutablePrivacyContract):
    """One pixel-space region that must be masked."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    kind: str = Field(min_length=1)


class ImageInput(ImmutablePrivacyContract):
    """Raw image supplied only to the local masking boundary."""

    image_id: str = Field(min_length=1)
    content: bytes = Field(repr=False)
    media_type: str = Field(default="image/png", min_length=1)
    source_reference: str | None = None
    processing_target: Literal["local", "external"] = "local"


class MaskedImage(ImmutablePrivacyContract):
    """Image derivative safe status returned by the masking boundary."""

    image_id: str = Field(min_length=1)
    content: bytes = Field(repr=False)
    media_type: str = Field(min_length=1)
    source_reference: str | None = None
    status: Literal["clean", "masked", "degraded", "blocked"]
    regions: tuple[SensitiveRegion, ...] = Field(default_factory=tuple)
    safe_for_external: bool = False
    reason: str = ""


class PrivacyResult(ImmutablePrivacyContract):
    """Input-stage privacy result consumed by workflow state."""

    text: str
    images: tuple[MaskedImage, ...] = Field(default_factory=tuple)
    findings: tuple[PrivacyFinding, ...] = Field(default_factory=tuple)
    redaction_count: int = Field(default=0, ge=0)
    blocked: bool = False
    degraded: bool = False
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)


class DLPResult(ImmutablePrivacyContract):
    """Output-stage sanitized answer and authorized citation set."""

    answer: str
    citations: tuple[EvidenceItem, ...] = Field(default_factory=tuple)
    findings: tuple[PrivacyFinding, ...] = Field(default_factory=tuple)
    redaction_count: int = Field(default=0, ge=0)
    dropped_citation_ids: tuple[str, ...] = Field(default_factory=tuple)


__all__ = [
    "DLPResult",
    "ImageInput",
    "ImmutablePrivacyContract",
    "MaskedImage",
    "PrivacyFinding",
    "PrivacyResult",
    "SensitiveRegion",
    "TextPrivacyResult",
]
