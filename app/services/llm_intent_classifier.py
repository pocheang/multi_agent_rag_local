"""Compatibility wrapper for the canonical query intent classifier."""

from app.services.query.intent_classifier import classify_intent_with_llm

__all__ = ["classify_intent_with_llm"]
