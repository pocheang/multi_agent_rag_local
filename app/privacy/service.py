"""Single deterministic privacy facade for input, retrieval context, and output."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.privacy.dlp import filter_output as apply_output_dlp
from app.privacy.dlp import mask_evidence
from app.privacy.image_masking import ImageMaskingService
from app.privacy.models import DLPResult, ImageInput, PrivacyResult
from app.privacy.text import inspect_text


class PrivacyService:
    """Coordinate deterministic privacy services without invoking an LLM."""

    def __init__(self, image_masking: ImageMaskingService | None = None) -> None:
        self._image_masking = image_masking or ImageMaskingService()

    def inspect_input(self, text: str, images: Sequence[ImageInput] = ()) -> PrivacyResult:
        inspected = inspect_text(text)
        masked_images = tuple(self._image_masking.mask(image) for image in images)
        blocked = any(image.status == "blocked" for image in masked_images)
        degraded = any(image.status == "degraded" for image in masked_images)
        reasons = tuple(image.reason for image in masked_images if image.reason)
        return PrivacyResult(
            text=inspected.text,
            images=masked_images,
            findings=inspected.findings,
            redaction_count=inspected.redaction_count,
            blocked=blocked,
            degraded=degraded,
            reason_codes=reasons,
        )

    def mask_context(self, items: Sequence[EvidenceItem], scope: AccessScope) -> tuple[EvidenceItem, ...]:
        return tuple(masked for item in items if (masked := mask_evidence(item, scope)) is not None)

    def filter_output(
        self,
        answer: str,
        citations: Sequence[EvidenceItem],
        scope: AccessScope,
    ) -> DLPResult:
        return apply_output_dlp(answer, citations, scope)


__all__ = ["PrivacyService"]
