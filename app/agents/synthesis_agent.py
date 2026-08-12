"""Compatibility exports for the canonical synthesis implementation."""

from app.agents.synthesizer.generation import (
    ANSWER_PROMPT,
    CASUAL_CHAT_HIGH_TEMPERATURE,
    REVIEW_PROMPT,
    SIMILARITY_STOP_THRESHOLD,
    SYNTHESIS_FALLBACK_MESSAGE,
    stream_synthesize_answer,
    synthesize_answer,
)

__all__ = [
    "SYNTHESIS_FALLBACK_MESSAGE",
    "CASUAL_CHAT_HIGH_TEMPERATURE",
    "SIMILARITY_STOP_THRESHOLD",
    "ANSWER_PROMPT",
    "REVIEW_PROMPT",
    "synthesize_answer",
    "stream_synthesize_answer",
]
