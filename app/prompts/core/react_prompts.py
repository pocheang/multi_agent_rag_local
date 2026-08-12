"""Core ReAct prompts; the system prompt comes from the canonical owner."""

from .canonical_agent_prompts import REACT_SYSTEM_PROMPT

__all__ = ["REACT_SYSTEM_PROMPT", "REACT_USER_PROMPT_TEMPLATE"]


REACT_USER_PROMPT_TEMPLATE = """**Question:** {question}

**Memory Context:** {memory_context}

**Previous Steps:**
{history}

**Your next reasoning step (JSON only):**"""
