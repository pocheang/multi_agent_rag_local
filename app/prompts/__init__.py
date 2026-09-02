"""Prompt templates used by the live agents.

This package used to re-export a large prompt library -- a 468-line
PromptManager, four "skills" catalogues, and separate router / intent / review /
synthesis / self-RAG modules -- of which exactly two names were ever consumed
from outside: ``build_router_prompt`` and ``QUERY_DECOMPOSITION_PROMPT``, both
defined in ``core.canonical_agent_prompts``. The rest was deleted on 2026-08-29.

The prompts the agents actually run live next to their agents:
``app/agents/synthesizer/templates.py``, ``app/agents/router/examples.py``,
``app/agents/planner/prompts.py``, ``app/agents/knowledge/prompts.py``.
"""

from app.prompts.core.canonical_agent_prompts import (
    ANSWER_PROMPT,
    NO_EVIDENCE_ANSWER_PROMPT,
    NO_EVIDENCE_REVIEW_PROMPT,
    QUERY_DECOMPOSITION_PROMPT,
    REVIEW_PROMPT,
    build_router_prompt,
)

__all__ = [
    "ANSWER_PROMPT",
    "NO_EVIDENCE_ANSWER_PROMPT",
    "NO_EVIDENCE_REVIEW_PROMPT",
    "QUERY_DECOMPOSITION_PROMPT",
    "REVIEW_PROMPT",
    "build_router_prompt",
]
