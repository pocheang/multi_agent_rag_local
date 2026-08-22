"""Language detection service for multilingual response system."""

import logging
import re

logger = logging.getLogger(__name__)

# Chinese character range: U+4E00 to U+9FFF (CJK Unified Ideographs)
CHINESE_PATTERN = re.compile(r"[一-鿿]")
ALPHANUM_PATTERN = re.compile(r"[a-zA-Z一-鿿0-9]")

# Detection threshold: if Chinese chars > 20% of alphanumeric, classify as Chinese
CHINESE_THRESHOLD = 0.20


def detect_language(text: str) -> str:
    """
    Detect language of input text.

    Args:
        text: User input text

    Returns:
        'zh' for Chinese, 'en' for English

    Algorithm:
        - Count Chinese characters (U+4E00 to U+9FFF)
        - Count total alphanumeric characters
        - If Chinese ratio > 20%, return 'zh'
        - Otherwise return 'en'
        - Default to 'zh' for empty/punctuation-only input
    """
    if not text or not text.strip():
        return "zh"  # Default to Chinese for empty input

    # Count Chinese characters
    chinese_chars = len(CHINESE_PATTERN.findall(text))

    # Count total alphanumeric characters (letters + Chinese + digits)
    total_alphanum = len(ALPHANUM_PATTERN.findall(text))

    # Handle edge case: no alphanumeric characters (pure punctuation)
    if total_alphanum == 0:
        return "zh"  # Default to Chinese

    # Calculate Chinese character ratio
    chinese_ratio = chinese_chars / total_alphanum

    # Determine language based on threshold
    detected = "zh" if chinese_ratio > CHINESE_THRESHOLD else "en"

    logger.debug(
        f"Language detection: {detected} (chinese_ratio={chinese_ratio:.2f}, "
        f"chinese_chars={chinese_chars}, total_alphanum={total_alphanum})"
    )

    return detected


def get_language_name(lang_code: str) -> str:
    """
    Convert language code to full name.

    Args:
        lang_code: 'zh' or 'en'

    Returns:
        'Chinese' or 'English'
    """
    return "Chinese" if lang_code == "zh" else "English"


def is_chinese_dominant(text: str) -> bool:
    """
    Quick check if text is primarily Chinese.

    Args:
        text: Input text

    Returns:
        True if Chinese characters dominate
    """
    return detect_language(text) == "zh"
