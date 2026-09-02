"""PDF loader with chart extraction support."""

import logging
from pathlib import Path

from langchain_core.documents import Document

from app.core.config import get_settings
from app.ingestion.extraction.charts import (
    chart_data_to_markdown,
    detect_chart_in_image,
    extract_chart_data_with_vision,
)

logger = logging.getLogger(__name__)


def extract_charts_from_pdf(path: Path, use_vision: bool = True, vision_model: str = "gpt-4-vision") -> list[Document]:
    """
    Extract charts from PDF and convert to structured text.

    Args:
        path: Path to PDF file
        use_vision: Use multimodal LLM for chart extraction
        vision_model: Vision model to use (gpt-4-vision, claude-3, etc.)

    Returns:
        List of Document objects with chart data
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    docs = []

    # Get API key from settings
    settings = get_settings()
    api_key = None
    if use_vision:
        if vision_model.startswith("gpt-4") or vision_model.startswith("gpt"):
            api_key = settings.openai_api_key
            if not api_key:
                logger.warning("OpenAI API key not configured, chart extraction will fail")
        elif vision_model.startswith("claude"):
            api_key = settings.anthropic_api_key
            if not api_key:
                logger.warning("Anthropic API key not configured, chart extraction will fail")

    try:
        # Use context manager for proper resource cleanup
        with open(path, "rb") as pdf_file:
            reader = PdfReader(pdf_file)

            for page_idx, page in enumerate(reader.pages, start=1):
                # Extract images from page
                try:
                    images = list(page.images or [])
                except Exception as e:
                    logger.warning(f"Failed to extract images from page {page_idx}: {e}")
                    images = []

                for img_idx, img_obj in enumerate(images, start=1):
                    img_bytes = getattr(img_obj, "data", None)
                    if not img_bytes:
                        continue

                    # Detect if image is a chart
                    detection = detect_chart_in_image(img_bytes)

                    if not detection.get("is_chart"):
                        continue

                    # Extract chart data
                    if use_vision:
                        chart_data = extract_chart_data_with_vision(img_bytes, model=vision_model, api_key=api_key)
                        chart_text = chart_data_to_markdown(chart_data)
                    else:
                        chart_text = "[Chart detected but vision extraction disabled]"

                    # Create document
                    doc = Document(
                        page_content=chart_text,
                        metadata={
                            "source": str(path),
                            "page": page_idx,
                            "image_index": img_idx,
                            "modality": "chart",
                            "chart_type": detection.get("chart_type", "unknown"),
                            "detection_confidence": detection.get("confidence", 0.0),
                        },
                    )
                    docs.append(doc)

    except Exception as e:
        logger.error(f"PDF chart extraction failed for {path.name}: {e}", exc_info=True)
        return docs

    return docs


def load_pdf_with_charts(path: Path, extract_charts: bool = True, vision_model: str = "gpt-4-vision") -> list[Document]:
    """
    Load PDF with chart extraction.

    Args:
        path: Path to PDF file
        extract_charts: Enable chart extraction
        vision_model: Vision model for chart extraction

    Returns:
        List of Document objects (text + charts)
    """
    from app.ingestion.loaders.pdf_loader import load_pdf_text

    # Load text content
    text_docs = load_pdf_text(path)

    # Extract charts if enabled
    if extract_charts:
        chart_docs = extract_charts_from_pdf(path, use_vision=True, vision_model=vision_model)
        return text_docs + chart_docs

    return text_docs
