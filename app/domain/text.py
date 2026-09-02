"""Framework-independent text normalization contracts."""

from __future__ import annotations


def normalize_string(value: str | None, lowercase: bool = False) -> str:
    """Strip a nullable string and optionally lowercase the result."""
    result = (value or "").strip()
    return result.lower() if lowercase else result


def normalize_optional(value: str | None, lowercase: bool = False) -> str | None:
    """Normalize a string, returning ``None`` when the normalized value is empty."""
    result = normalize_string(value, lowercase)
    return result or None


def is_empty(value: str | None) -> bool:
    """Return whether a nullable string is empty after normalization."""
    return not normalize_string(value)
