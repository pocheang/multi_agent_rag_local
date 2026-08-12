"""Compatibility exports for comparison and timeline prompts."""

from .skills.comparison_timeline_prompts import (
    COMPARE_ENTITIES_SYSTEM_PROMPT,
    COMPARE_ENTITIES_USER_PROMPT_TEMPLATE,
    TIMELINE_BUILDER_SYSTEM_PROMPT,
    TIMELINE_BUILDER_USER_PROMPT_TEMPLATE,
    get_compare_entities_prompts,
    get_timeline_builder_prompts,
)

__all__ = [
    "COMPARE_ENTITIES_SYSTEM_PROMPT",
    "COMPARE_ENTITIES_USER_PROMPT_TEMPLATE",
    "TIMELINE_BUILDER_SYSTEM_PROMPT",
    "TIMELINE_BUILDER_USER_PROMPT_TEMPLATE",
    "get_compare_entities_prompts",
    "get_timeline_builder_prompts",
]
