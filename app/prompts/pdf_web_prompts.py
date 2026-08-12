"""Compatibility exports for PDF and Web prompts."""

from .skills.pdf_web_prompts import (
    PDF_TEXT_READER_SYSTEM_PROMPT,
    PDF_TEXT_READER_USER_PROMPT_TEMPLATE,
    WEB_FACT_CHECK_SYSTEM_PROMPT,
    WEB_FACT_CHECK_USER_PROMPT_TEMPLATE,
    get_pdf_text_reader_prompts,
    get_web_fact_check_prompts,
)

__all__ = [
    "PDF_TEXT_READER_SYSTEM_PROMPT",
    "PDF_TEXT_READER_USER_PROMPT_TEMPLATE",
    "WEB_FACT_CHECK_SYSTEM_PROMPT",
    "WEB_FACT_CHECK_USER_PROMPT_TEMPLATE",
    "get_pdf_text_reader_prompts",
    "get_web_fact_check_prompts",
]
