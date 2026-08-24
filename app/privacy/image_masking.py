"""Local sensitive-region detection and deterministic raster masking."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from typing import Protocol

from app.core.config import Settings, get_settings
from app.privacy.models import ImageInput, MaskedImage, SensitiveRegion
from app.privacy.text import INPUT_KINDS, inspect_text


class ImageMaskingUnavailable(RuntimeError):
    """Raised when the configured local detector cannot inspect an image."""


class SensitiveRegionDetector(Protocol):
    def detect(self, image: ImageInput) -> Sequence[SensitiveRegion]: ...


class TesseractSensitiveRegionDetector:
    """Use the configured local OCR engine to locate sensitive text boxes."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def detect(self, image: ImageInput) -> Sequence[SensitiveRegion]:
        try:
            import pytesseract
            from PIL import Image
            from pytesseract import Output
        except ImportError as exc:
            raise ImageMaskingUnavailable("local OCR detector is unavailable") from exc

        if self._settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_cmd
        try:
            with Image.open(BytesIO(image.content)) as pil_image:
                data = pytesseract.image_to_data(
                    pil_image,
                    lang=self._settings.tesseract_lang or "eng",
                    output_type=Output.DICT,
                )
        except Exception as exc:
            raise ImageMaskingUnavailable("local OCR sensitive-region detection failed") from exc

        regions: list[SensitiveRegion] = []
        words = list(data.get("text", []) or [])
        for index, word in enumerate(words):
            inspection = inspect_text(str(word or ""), kinds=INPUT_KINDS)
            if not inspection.findings:
                continue
            try:
                regions.append(
                    SensitiveRegion(
                        x=max(0, int(data["left"][index])),
                        y=max(0, int(data["top"][index])),
                        width=max(1, int(data["width"][index])),
                        height=max(1, int(data["height"][index])),
                        kind=inspection.findings[0].kind,
                    )
                )
            except (IndexError, KeyError, TypeError, ValueError):
                continue
        return tuple(regions)


class ImageMaskingService:
    """Mask detected regions and fail closed before external image processing."""

    def __init__(self, detector: SensitiveRegionDetector | None = None) -> None:
        self._detector = detector or TesseractSensitiveRegionDetector()

    def mask(self, image: ImageInput) -> MaskedImage:
        try:
            regions = tuple(self._detector.detect(image))
        except ImageMaskingUnavailable as exc:
            if image.processing_target == "external":
                return MaskedImage(
                    image_id=image.image_id,
                    content=b"",
                    media_type=image.media_type,
                    source_reference=image.source_reference,
                    status="blocked",
                    safe_for_external=False,
                    reason=str(exc),
                )
            return MaskedImage(
                image_id=image.image_id,
                content=image.content,
                media_type=image.media_type,
                source_reference=image.source_reference,
                status="degraded",
                safe_for_external=False,
                reason=str(exc),
            )

        if not regions:
            return MaskedImage(
                image_id=image.image_id,
                content=image.content,
                media_type=image.media_type,
                source_reference=image.source_reference,
                status="clean",
                safe_for_external=True,
            )

        try:
            from PIL import Image, ImageDraw

            with Image.open(BytesIO(image.content)) as pil_image:
                output_format = pil_image.format or _format_for_media_type(image.media_type)
                masked = pil_image.convert("RGB")
                drawing = ImageDraw.Draw(masked)
                for region in regions:
                    drawing.rectangle(
                        (
                            region.x,
                            region.y,
                            region.x + region.width,
                            region.y + region.height,
                        ),
                        fill="black",
                    )
                buffer = BytesIO()
                masked.save(buffer, format=output_format)
        except Exception as exc:
            if image.processing_target == "external":
                return MaskedImage(
                    image_id=image.image_id,
                    content=b"",
                    media_type=image.media_type,
                    source_reference=image.source_reference,
                    status="blocked",
                    regions=regions,
                    safe_for_external=False,
                    reason="sensitive image masking failed",
                )
            return MaskedImage(
                image_id=image.image_id,
                content=image.content,
                media_type=image.media_type,
                source_reference=image.source_reference,
                status="degraded",
                regions=regions,
                safe_for_external=False,
                reason=f"sensitive image masking failed: {type(exc).__name__}",
            )

        return MaskedImage(
            image_id=image.image_id,
            content=buffer.getvalue(),
            media_type=image.media_type,
            source_reference=image.source_reference,
            status="masked",
            regions=regions,
            safe_for_external=True,
        )


def _format_for_media_type(media_type: str) -> str:
    return {
        "image/jpeg": "JPEG",
        "image/jpg": "JPEG",
        "image/webp": "WEBP",
        "image/tiff": "TIFF",
    }.get(str(media_type or "").lower(), "PNG")


__all__ = [
    "ImageMaskingService",
    "ImageMaskingUnavailable",
    "SensitiveRegionDetector",
    "TesseractSensitiveRegionDetector",
]
