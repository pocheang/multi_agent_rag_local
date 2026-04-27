"""Utility functions for document ingestion."""

from app.ingestion.utils.ocr_utils import (
    ocr_image_bytes,
    normalize_ocr_text,
    score_ocr_text,
    parse_psm_modes,
    autorotate_image,
    build_ocr_candidates,
    run_ocr_with_candidates,
)
from app.ingestion.utils.vision_utils import (
    describe_image_with_vision,
    build_vision_summary,
    vision_prompt,
)
from app.ingestion.utils.people_detection import (
    detect_people_in_image,
    build_people_summary,
)

__all__ = [
    "ocr_image_bytes",
    "normalize_ocr_text",
    "score_ocr_text",
    "parse_psm_modes",
    "autorotate_image",
    "build_ocr_candidates",
    "run_ocr_with_candidates",
    "describe_image_with_vision",
    "build_vision_summary",
    "vision_prompt",
    "detect_people_in_image",
    "build_people_summary",
]
