"""Compatibility exports for quick retrieval prompts."""

from .retrieval.rag_quick_retrieval_prompts import (
    CONTEXT_SUMMARY_SYSTEM_PROMPT,
    CONTEXT_SUMMARY_USER_PROMPT_TEMPLATE,
    DOCUMENT_SEARCH_SYSTEM_PROMPT,
    DOCUMENT_SEARCH_USER_PROMPT_TEMPLATE,
    INFORMATION_EXTRACTION_SYSTEM_PROMPT,
    INFORMATION_EXTRACTION_USER_PROMPT_TEMPLATE,
    KEYWORD_SEARCH_SYSTEM_PROMPT,
    KEYWORD_SEARCH_USER_PROMPT_TEMPLATE,
    QUICK_ANSWER_SYSTEM_PROMPT,
    QUICK_ANSWER_USER_PROMPT_TEMPLATE,
    get_context_summary_prompts,
    get_document_search_prompts,
    get_information_extraction_prompts,
    get_keyword_search_prompts,
    get_quick_answer_prompts,
)

__all__ = [
    "QUICK_ANSWER_SYSTEM_PROMPT",
    "QUICK_ANSWER_USER_PROMPT_TEMPLATE",
    "DOCUMENT_SEARCH_SYSTEM_PROMPT",
    "DOCUMENT_SEARCH_USER_PROMPT_TEMPLATE",
    "INFORMATION_EXTRACTION_SYSTEM_PROMPT",
    "INFORMATION_EXTRACTION_USER_PROMPT_TEMPLATE",
    "CONTEXT_SUMMARY_SYSTEM_PROMPT",
    "CONTEXT_SUMMARY_USER_PROMPT_TEMPLATE",
    "KEYWORD_SEARCH_SYSTEM_PROMPT",
    "KEYWORD_SEARCH_USER_PROMPT_TEMPLATE",
    "get_quick_answer_prompts",
    "get_document_search_prompts",
    "get_information_extraction_prompts",
    "get_context_summary_prompts",
    "get_keyword_search_prompts",
]
