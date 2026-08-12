"""Compatibility exports for canonical agent prompts."""

from .core.canonical_agent_prompts import (
    ANSWER_PROMPT,
    QUERY_DECOMPOSITION_PROMPT,
    REACT_SYSTEM_PROMPT,
    REVIEW_PROMPT,
    ROUTER_PROMPT_TEMPLATE,
    build_router_prompt,
)

__all__ = [
    "ANSWER_PROMPT",
    "QUERY_DECOMPOSITION_PROMPT",
    "REACT_SYSTEM_PROMPT",
    "REVIEW_PROMPT",
    "ROUTER_PROMPT_TEMPLATE",
    "build_router_prompt",
]
