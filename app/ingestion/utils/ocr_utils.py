"""OCR utilities for image processing."""

import os
import re
from io import BytesIO
from pathlib import Path

from langchain_core.documents import Document

from app.core.config import get_settings


def normalize_ocr_text(text: str) -> str:
    """Normalize OCR text by removing extra whitespace."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines).strip()


def score_ocr_text(text: str) -> int:
    """Score OCR text quality based on length and character types."""
    compact = "".join(ch for ch in (text or "") if not ch.isspace())
    if not compact:
        return 0
    alnum = sum(1 for ch in compact if ch.isalnum())
    cjk = sum(1 for ch in compact if "一" <= ch <= "鿿")
    # Prefer longer results and those containing meaningful characters.
    return len(compact) + alnum + (2 * cjk)


def parse_psm_modes(raw: str) -> list[int]:
    """Parse PSM (Page Segmentation Mode) values from comma-separated string."""
    values = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            psm = int(part)
        except ValueError:
            continue
        if 0 <= psm <= 13:
            values.append(psm)
    return values or [6, 11, 3]


def autorotate_image(image, pytesseract_module):
    """Auto-rotate image based on OSD (Orientation and Script Detection)."""
    try:
        osd = pytesseract_module.image_to_osd(image)
        match = re.search(r"Rotate:\s*(\d+)", osd or "")
        degrees = int(match.group(1)) if match else 0
    except Exception:
        degrees = 0
    if degrees in {90, 180, 270}:
        return image.rotate(360 - degrees, expand=True)
    return image


def build_ocr_candidates(image, settings, pil_imageops):
    """Build multiple image preprocessing candidates for OCR."""
    candidates: list[tuple[str, object]] = [("raw", image)]
    if not settings.ocr_preprocess_enabled:
        return candidates

    width, height = image.size
    min_side = min(width, height)
    if min_side > 0 and settings.ocr_upscale_min_side > 0 and min_side < settings.ocr_upscale_min_side:
        try:
            resampling = getattr(getattr(image, "Resampling", None), "LANCZOS", None)
            if resampling is None:
                from PIL import Image

                resampling = Image.LANCZOS
            scale = settings.ocr_upscale_min_side / float(min_side)
            upscaled = image.resize((int(width * scale), int(height * scale)), resampling)
            candidates.append(("upscaled", upscaled))
        except Exception:
            pass

    base_variants = list(candidates)
    for base_name, base_image in base_variants:
        try:
            gray = pil_imageops.grayscale(base_image)
            candidates.append((f"{base_name}_gray", gray))
            high_contrast = pil_imageops.autocontrast(gray)
            candidates.append((f"{base_name}_autocontrast", high_contrast))
            binary = high_contrast.point(lambda x: 255 if x > 170 else 0)
            candidates.append((f"{base_name}_binary", binary))
            inverted = pil_imageops.invert(high_contrast)
            candidates.append((f"{base_name}_inverted", inverted))
        except Exception:
            continue

    return candidates


def run_ocr_with_candidates(image, settings, pytesseract_module, pil_imageops):
    """Run OCR with multiple preprocessing candidates and PSM modes."""
    image = autorotate_image(image, pytesseract_module)
    candidates = build_ocr_candidates(image, settings, pil_imageops)
    psm_modes = parse_psm_modes(settings.ocr_psm_modes)

    lang = settings.tesseract_lang or "chi_sim+eng"
    best_text = ""
    best_score = 0
    best_variant = "raw"
    best_psm = ""
    last_error = ""

    for variant_name, candidate in candidates:
        for psm in psm_modes:
            config = f"--oem 3 --psm {psm}"
            try:
                raw = pytesseract_module.image_to_string(candidate, lang=lang, config=config) or ""
                text = normalize_ocr_text(raw)
                score = score_ocr_text(text)
                if score > best_score:
                    best_text = text
                    best_score = score
                    best_variant = variant_name
                    best_psm = str(psm)
            except Exception as e:
                last_error = str(e)

    if best_text:
        return best_text, best_variant, best_psm, ""

    # Last fallback: default OCR call without custom config.
    try:
        raw = pytesseract_module.image_to_string(image) or ""
        text = normalize_ocr_text(raw)
        if text:
            return text, "raw_fallback", "", ""
    except Exception as e:
        last_error = str(e)

    return "", "", "", last_error


def ocr_image_bytes(img_bytes: bytes, source: Path, page: int | None = None, image_index: int | None = None) -> list[Document]:
    """OCR image bytes and return Document with metadata."""
    try:
        from PIL import Image, ImageOps
    except Exception:
        return []

    try:
        image = Image.open(BytesIO(img_bytes))
    except Exception:
        return []

    from app.ingestion.utils.people_detection import build_people_summary, detect_people_in_image
    from app.ingestion.utils.vision_utils import build_vision_summary, describe_image_with_vision

    width, height = image.size
    mode = image.mode or "unknown"
    file_format = (image.format or "unknown").lower()
    summary = f"[image_meta] format={file_format}; mode={mode}; size={width}x{height}."

    metadata = {
        "source": str(source),
        "modality": "image_ocr",
        "width": width,
        "height": height,
        "image_mode": mode,
        "image_format": file_format,
    }
    if page is not None:
        metadata["page"] = page
    if image_index is not None:
        metadata["image_index"] = image_index

    settings = get_settings()
    people_info = detect_people_in_image(image, settings)
    metadata["person_detection_status"] = str(people_info.get("status", "unknown"))
    metadata["person_count"] = int(people_info.get("person_count", 0))
    metadata["face_count"] = int(people_info.get("face_count", 0))
    metadata["human_present"] = bool(people_info.get("human_present", False))
    metadata["person_detector_mode"] = str(people_info.get("detector_mode", "face"))
    people_summary = build_people_summary(people_info)
    vision_info = describe_image_with_vision(img_bytes, settings)
    metadata["image_caption_status"] = str(vision_info.get("status", "unknown"))
    metadata["image_caption_model"] = str(vision_info.get("model", "") or "")
    if vision_info.get("caption"):
        metadata["image_caption"] = str(vision_info.get("caption", ""))
    if vision_info.get("error"):
        metadata["image_caption_error"] = str(vision_info.get("error", ""))
    vision_summary = build_vision_summary(vision_info)

    try:
        import pytesseract
    except Exception:
        metadata["ocr_status"] = "pytesseract_missing"
        content = f"{summary}\n{people_summary}\n{vision_summary}\n[image_ocr_error]\npytesseract not installed"
        return [Document(page_content=content, metadata=metadata)]

    if settings.tessdata_prefix:
        os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    ocr_text, ocr_variant, ocr_psm, ocr_error = run_ocr_with_candidates(
        image=image,
        settings=settings,
        pytesseract_module=pytesseract,
        pil_imageops=ImageOps,
    )
    ocr_status = "ok"

    if not ocr_text:
        err_lower = ocr_error.lower()
        if "tesseract is not installed" in err_lower or "tesseractnotfounderror" in err_lower:
            ocr_status = "engine_not_found"
            reason = "Tesseract executable not found"
        elif "failed loading language" in err_lower or "error opening data file" in err_lower:
            ocr_status = "language_data_missing"
            reason = "Tesseract language data missing or TESSDATA_PREFIX not set correctly"
        elif ocr_error:
            ocr_status = "ocr_runtime_error"
            reason = f"OCR runtime error: {ocr_error}"
        else:
            ocr_status = "no_text_detected"
            reason = "OCR ran but no text detected (image may be blank/low quality)"
        metadata["ocr_status"] = ocr_status
        metadata["ocr_error"] = ocr_error
        content = f"{summary}\n{people_summary}\n{vision_summary}\n[image_ocr_error]\n{reason}"
        return [Document(page_content=content, metadata=metadata)]

    metadata["ocr_status"] = ocr_status
    metadata["ocr_variant"] = ocr_variant
    metadata["ocr_psm"] = ocr_psm
    content = f"{summary}\n{people_summary}\n{vision_summary}\n[image_ocr]\n{ocr_text}"

    return [Document(page_content=content, metadata=metadata)]
