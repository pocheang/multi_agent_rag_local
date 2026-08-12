"""Compatibility exports for historical ingestion utility imports."""

from app.ingestion.extraction.ocr import (
    normalize_ocr_text,
    ocr_image_bytes,
    parse_psm_modes,
    run_ocr_with_candidates,
)
from app.ingestion.extraction.people import build_people_summary, detect_people_in_image
from app.ingestion.extraction.vision import build_vision_summary, describe_image_with_vision

__all__ = [
    "build_people_summary",
    "build_vision_summary",
    "describe_image_with_vision",
    "detect_people_in_image",
    "normalize_ocr_text",
    "ocr_image_bytes",
    "parse_psm_modes",
    "run_ocr_with_candidates",
]

