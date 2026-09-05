"""Chart and graph detection and extraction from PDFs."""

import logging

from app.privacy.image_egress import bytes_for_external_provider
from app.services.security.outbound_redaction import redact_messages_for_provider

logger = logging.getLogger(__name__)

# Configuration
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_DIMENSION = 2048  # pixels


def _resize_image_if_needed(image_bytes: bytes, max_size_bytes: int = MAX_IMAGE_SIZE_BYTES) -> bytes:
    """
    Resize image if it exceeds size limit.

    Args:
        image_bytes: Original image bytes
        max_size_bytes: Maximum allowed size in bytes

    Returns:
        Resized image bytes (or original if under limit)
    """
    if len(image_bytes) <= max_size_bytes:
        return image_bytes

    try:
        from io import BytesIO

        from PIL import Image

        logger.info(f"Resizing large image ({len(image_bytes)} bytes) to fit {max_size_bytes} bytes")

        img = Image.open(BytesIO(image_bytes))

        # Calculate scale factor
        scale = (max_size_bytes / len(image_bytes)) ** 0.5
        new_width = int(img.width * scale)
        new_height = int(img.height * scale)

        # Ensure dimensions don't exceed maximum
        if new_width > MAX_IMAGE_DIMENSION or new_height > MAX_IMAGE_DIMENSION:
            aspect_ratio = img.width / img.height
            if aspect_ratio > 1:
                new_width = MAX_IMAGE_DIMENSION
                new_height = int(MAX_IMAGE_DIMENSION / aspect_ratio)
            else:
                new_height = MAX_IMAGE_DIMENSION
                new_width = int(MAX_IMAGE_DIMENSION * aspect_ratio)

        # Resize
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save to bytes
        output = BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        resized_bytes = output.getvalue()

        logger.info(f"Resized image from {len(image_bytes)} to {len(resized_bytes)} bytes")
        return resized_bytes

    except Exception as e:
        logger.exception(f"Image resize failed: {e}")
        # Return original if resize fails
        return image_bytes


def detect_chart_in_image(image_bytes: bytes) -> dict[str, any]:
    """
    Detect if image contains a chart/graph.

    Args:
        image_bytes: Image bytes

    Returns:
        Dict with detection results:
        - is_chart: bool
        - chart_type: str (bar, line, pie, scatter, etc.)
        - confidence: float
    """
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(image_bytes))

        # Simple heuristics for chart detection
        # Real implementation would use ML model
        width, height = img.size

        # Charts are usually rectangular and not too small
        if width < 200 or height < 200:
            return {"is_chart": False, "chart_type": None, "confidence": 0.0}

        # Check aspect ratio (charts usually have reasonable aspect ratios)
        aspect_ratio = width / height
        if aspect_ratio < 0.3 or aspect_ratio > 3.0:
            return {"is_chart": False, "chart_type": None, "confidence": 0.3}

        # Basic detection - assume it might be a chart
        # In production, use a trained model
        return {"is_chart": True, "chart_type": "unknown", "confidence": 0.6, "width": width, "height": height}

    except Exception:
        logger.exception("Chart detection failed")
        return {"is_chart": False, "chart_type": None, "confidence": 0.0}


def extract_chart_data_with_vision(
    image_bytes: bytes, model: str = "gpt-4o", api_key: str | None = None
) -> dict[str, any]:
    """
    Extract data from chart using multimodal LLM.

    Args:
        image_bytes: Image bytes
        model: Model to use (gpt-4o, gpt-4-turbo, claude-3-5-sonnet, etc.)
        api_key: API key for the model

    Returns:
        Dict with extracted data:
        - chart_type: str
        - title: str
        - data: list of dicts
        - description: str
    """
    try:
        # Resize image if too large (prevent memory issues)
        image_bytes = _resize_image_if_needed(image_bytes)

        if model.startswith("gpt-4") or model.startswith("gpt"):
            provider = "openai"
        elif model.startswith("claude"):
            provider = "anthropic"
        else:
            logger.error(f"Unsupported model: {model}")
            return {"error": f"Unsupported model: {model}"}

        # Both branches below are external providers, and this is the second live
        # path that base64s a user's image into a request body. It reached
        # OpenAI and Anthropic uninspected until 2026-09-05 -- the outbound
        # redactor applied further down is a *text* control and leaves the data
        # URI byte-identical. Masking is decided in one place for both send
        # paths; see app/privacy/image_egress.py.
        safe_bytes, blocked = bytes_for_external_provider(image_bytes, provider)
        if blocked:
            logger.info(f"chart_vision_blocked provider={provider} reason={blocked}")
            return {"error": f"image masking did not clear this chart for {provider}: {blocked}"}

        if provider == "openai":
            return _extract_with_openai(safe_bytes, api_key, model)
        return _extract_with_anthropic(safe_bytes, api_key, model)

    except Exception as e:
        logger.exception(f"Chart extraction failed: {e}")
        return {"error": str(e)}


def _extract_json_from_text(text: str) -> dict | None:
    """
    Extract JSON from text with multiple strategies.

    Args:
        text: Text containing JSON

    Returns:
        Parsed JSON dict or None
    """
    import json
    import re

    # Strategy 1: Look for JSON code block
    code_block_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError as e:
            logger.debug(f"JSON code block parse failed: {e}")

    # Strategy 2: Find first complete JSON object
    brace_count = 0
    start_idx = text.find("{")
    if start_idx == -1:
        return None

    for i in range(start_idx, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                try:
                    return json.loads(text[start_idx : i + 1])
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON object parse failed: {e}")
                break

    return None


def _extract_with_openai(image_bytes: bytes, api_key: str | None, model: str = "gpt-4o") -> dict:
    """Extract chart data using OpenAI GPT-4o/GPT-4-turbo."""
    try:
        import base64

        from openai import OpenAI

        if not api_key:
            logger.error("OpenAI API key not provided")
            return {"error": "OpenAI API key not configured"}

        # Encode image
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        client = OpenAI(api_key=api_key)

        prompt = """Analyze this chart/graph and extract the data in structured format.

Please provide:
1. Chart type (bar, line, pie, scatter, etc.)
2. Chart title
3. Axis labels (if applicable)
4. Data points in JSON format
5. Brief description of what the chart shows

Format your response as JSON:
{
  "chart_type": "...",
  "title": "...",
  "x_label": "...",
  "y_label": "...",
  "data": [{"label": "...", "value": ...}, ...],
  "description": "..."
}"""

        # Use latest model
        messages = redact_messages_for_provider(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    ],
                }
            ],
            provider="openai",
        )

        response = client.chat.completions.create(model=model, messages=messages, max_tokens=1000)

        # Parse response
        content = response.choices[0].message.content

        # Try to extract JSON
        data = _extract_json_from_text(content)
        if data:
            return data
        else:
            logger.warning("Could not extract JSON from response, returning raw text")
            return {"description": content, "raw_response": True}

    except ImportError:
        logger.exception("OpenAI library not installed")
        return {"error": "OpenAI library not installed"}
    except Exception as e:
        logger.exception(f"OpenAI extraction failed: {e}")
        return {"error": str(e)}


def _extract_with_anthropic(image_bytes: bytes, api_key: str | None, model: str = "claude-3-5-sonnet-20241022") -> dict:
    """Extract chart data using Anthropic Claude."""
    try:
        import base64

        from anthropic import Anthropic

        if not api_key:
            logger.error("Anthropic API key not provided")
            return {"error": "Anthropic API key not configured"}

        # Encode image
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        client = Anthropic(api_key=api_key)

        prompt = """Analyze this chart/graph and extract the data in structured format.

Please provide:
1. Chart type (bar, line, pie, scatter, etc.)
2. Chart title
3. Axis labels (if applicable)
4. Data points in JSON format
5. Brief description of what the chart shows

Format your response as JSON."""

        messages = redact_messages_for_provider(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            provider="anthropic",
        )

        message = client.messages.create(model=model, max_tokens=1000, messages=messages)

        # Parse response
        content = message.content[0].text

        # Try to extract JSON
        data = _extract_json_from_text(content)
        if data:
            return data
        else:
            logger.warning("Could not extract JSON from response, returning raw text")
            return {"description": content, "raw_response": True}

    except ImportError:
        logger.exception("Anthropic library not installed")
        return {"error": "Anthropic library not installed"}
    except Exception as e:
        logger.exception(f"Anthropic extraction failed: {e}")
        return {"error": str(e)}


def chart_data_to_markdown(chart_data: dict) -> str:
    """
    Convert extracted chart data to Markdown format.

    Args:
        chart_data: Extracted chart data

    Returns:
        Markdown formatted text
    """
    if "error" in chart_data:
        return f"[Chart extraction error: {chart_data['error']}]"

    lines = []

    # Title
    if chart_data.get("title"):
        lines.append(f"## {chart_data['title']}")
        lines.append("")

    # Chart type
    if chart_data.get("chart_type"):
        lines.append(f"**Chart Type**: {chart_data['chart_type']}")
        lines.append("")

    # Description
    if chart_data.get("description"):
        lines.append(chart_data["description"])
        lines.append("")

    # Data table
    if chart_data.get("data"):
        lines.append("### Data")
        lines.append("")

        data = chart_data["data"]
        if isinstance(data, list) and len(data) > 0:
            # Create table
            if isinstance(data[0], dict):
                # Get keys
                keys = list(data[0].keys())
                # Header
                lines.append("| " + " | ".join(keys) + " |")
                lines.append("| " + " | ".join(["---"] * len(keys)) + " |")
                # Rows
                for row in data:
                    values = [str(row.get(k, "")) for k in keys]
                    lines.append("| " + " | ".join(values) + " |")
            else:
                # Simple list
                for item in data:
                    lines.append(f"- {item}")

    return "\n".join(lines)
