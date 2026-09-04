"""增强的 OCR 工具，支持基于位置的结构识别 - 重构版."""

import logging
import os
from io import BytesIO
from pathlib import Path

from langchain_core.documents import Document

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_base_metadata(image, source: Path, page: int | None, image_index: int | None) -> tuple[dict, str]:
    """构建基础 metadata 和 summary."""
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

    return metadata, summary


def _add_vision_metadata(metadata: dict, image, img_bytes: bytes, settings) -> tuple[str, str]:
    """添加人脸检测和图像描述信息."""
    from app.ingestion.extraction.people import detect_people_in_image
    from app.ingestion.extraction.vision import build_vision_summary, describe_image_with_vision

    # 人脸检测
    people_info = detect_people_in_image(image, settings)
    metadata["person_detection_status"] = str(people_info.get("status", "unknown"))
    metadata["person_count"] = int(people_info.get("person_count", 0))
    metadata["face_count"] = int(people_info.get("face_count", 0))
    metadata["human_present"] = bool(people_info.get("human_present", False))
    metadata["person_detector_mode"] = str(people_info.get("detector_mode", "face"))

    # 图像描述
    vision_info = describe_image_with_vision(img_bytes, settings)
    metadata["image_caption_status"] = str(vision_info.get("status", "unknown"))
    metadata["image_caption_model"] = str(vision_info.get("model", "") or "")
    if vision_info.get("caption"):
        metadata["image_caption"] = str(vision_info.get("caption", ""))
    if vision_info.get("error"):
        metadata["image_caption_error"] = str(vision_info.get("error", ""))
    vision_summary = build_vision_summary(vision_info)

    return vision_summary


def _add_block_statistics(metadata: dict, blocks) -> None:
    """添加文本块统计信息."""
    metadata["text_blocks_count"] = len(blocks)
    block_types = {}
    for block in blocks:
        block_types[block.type] = block_types.get(block.type, 0) + 1
    metadata["block_types"] = block_types


def _try_paddleocr(img_bytes: bytes, width: int, height: int, metadata: dict) -> tuple[str | None, dict]:
    """尝试使用 PaddleOCR 进行结构识别."""
    try:
        from paddleocr import PaddleOCR

        from app.ingestion.extraction.layout import integrate_with_paddleocr
        from app.ingestion.processing.text_structure import blocks_to_markdown

        # 初始化 PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

        # 执行 OCR
        result = ocr.ocr(img_bytes, cls=True)

        if result and result[0]:
            # 基于位置的结构识别
            structured_blocks = integrate_with_paddleocr(result[0], width, height)

            # 转换为 Markdown
            structured_text = blocks_to_markdown(structured_blocks)

            metadata["ocr_status"] = "ok"
            metadata["ocr_engine"] = "paddleocr"
            metadata["ocr_method"] = "layout_based"
            _add_block_statistics(metadata, structured_blocks)

            return structured_text, metadata

    except ImportError:
        # PaddleOCR 未安装
        pass
    except Exception as e:
        # PaddleOCR 执行失败
        metadata["paddleocr_error"] = str(e)

    return None, metadata


def _try_tesseract(image, settings, metadata: dict) -> tuple[str | None, dict, str]:
    """尝试使用 Tesseract 进行 OCR."""
    from app.ingestion.extraction.ocr import run_ocr_with_candidates

    try:
        import pytesseract
        from PIL import ImageOps
    except ImportError:
        logger.warning("pytesseract or PIL not available")
        metadata["ocr_status"] = "pytesseract_missing"
        return None, metadata, "pytesseract not installed"

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
        return None, metadata, reason

    # Tesseract 成功，应用文本结构识别
    from app.ingestion.processing.text_structure import blocks_to_markdown, structure_ocr_text

    structured_blocks = structure_ocr_text(ocr_text)
    structured_text = blocks_to_markdown(structured_blocks)

    metadata["ocr_status"] = "ok"
    metadata["ocr_engine"] = "tesseract"
    metadata["ocr_method"] = "text_based"
    metadata["ocr_variant"] = ocr_variant
    metadata["ocr_psm"] = ocr_psm
    _add_block_statistics(metadata, structured_blocks)

    return structured_text, metadata, ""


def ocr_image_bytes_with_structure(
    img_bytes: bytes, source: Path, page: int | None = None, image_index: int | None = None, use_layout: bool = True
) -> list[Document]:
    """OCR image bytes with optional layout-based structure recognition.

    Args:
        img_bytes: Image bytes
        source: Source file path
        page: Page number
        image_index: Image index within page
        use_layout: If True, use PaddleOCR for layout-based structure recognition.
                   If False or PaddleOCR unavailable, fallback to Tesseract.

    Returns:
        List of Document objects with structured content
    """
    try:
        from PIL import Image
    except ImportError:
        logger.warning("PIL not available for OCR enhanced processing")
        return []

    try:
        image = Image.open(BytesIO(img_bytes))
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to open image bytes for OCR: {e}")
        return []

    settings = get_settings()

    # 构建基础信息
    metadata, summary = _build_base_metadata(image, source, page, image_index)
    vision_summary = _add_vision_metadata(metadata, image, img_bytes, settings)

    # 尝试 PaddleOCR（如果启用）
    if use_layout:
        structured_text, metadata = _try_paddleocr(img_bytes, image.width, image.height, metadata)
        if structured_text:
            content = f"{summary}\n{vision_summary}\n[image_ocr_structured]\n{structured_text}"
            return [Document(page_content=content, metadata=metadata)]

    # 降级到 Tesseract
    structured_text, metadata, error_reason = _try_tesseract(image, settings, metadata)

    if structured_text:
        content = f"{summary}\n{vision_summary}\n[image_ocr_structured]\n{structured_text}"
    else:
        content = f"{summary}\n{vision_summary}\n[image_ocr_error]\n{error_reason}"

    return [Document(page_content=content, metadata=metadata)]
