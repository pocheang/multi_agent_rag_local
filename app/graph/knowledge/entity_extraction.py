"""
Multi-stage entity extraction with validation.

Task 6: Graph RAG - Robust Entity Extraction

Implements:
- Stage 1: Rule-based NER for common patterns
- Stage 2: LLM-based extraction for complex cases
- Cross-validation between methods
- Fuzzy matching for entity linking (Levenshtein distance â‰¤ 2)
"""

import logging
import re
from typing import Any

from app.domain.text import normalize_string

logger = logging.getLogger(__name__)

# Entity aliases (from graph_tools.py)
_ENTITY_ALIASES = {
    "ai": "artificial intelligence",
    "a.i.": "artificial intelligence",
    "llm": "large language model",
    "llms": "large language model",
    "å¤§æ¨¡åž‹": "large language model",
    "ç½‘ç»œå®‰å…¨": "cybersecurity",
    "èµ„å®‰": "cybersecurity",
}

# Patterns for rule-based extraction
# 1. Acronyms: 2-5 uppercase letters possibly with dots, optionally followed by 's' for plural
ACRONYM_PATTERN = re.compile(r"\b[A-Z]\.?[A-Z]\.?[A-Z]?\.?[A-Z]?\.?[A-Z]?s?\b")

# 2. Capitalized words (proper nouns): consecutive capitalized words
CAPITALIZED_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")

# 3. Chinese technical terms: 2+ consecutive Chinese characters
CHINESE_TERM_PATTERN = re.compile(r"[ä¸€-é¿¿]{2,}")

# 4. Technical terms with numbers/hyphens: GPT-4, Python3, etc.
TECHNICAL_TERM_PATTERN = re.compile(r"\b[A-Z][a-zA-Z0-9]*[-]?[0-9]*[a-zA-Z0-9]*\b")

# 5. Multi-word technical phrases (noun phrases)
TECHNICAL_PHRASE_PATTERN = re.compile(
    r"\b(?:transformer|attention|architecture|mechanism|injection|neural|network|deep|machine|learning|language|model|processing)\b",
    re.IGNORECASE,
)

# Common stopwords to exclude
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "can",
    "this",
    "that",
    "these",
    "those",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
}


def extract_entities_rule_based(query: str) -> list[dict[str, Any]]:
    """
    Stage 1: Extract entities using rule-based NER patterns.

    Args:
        query: Input query string

    Returns:
        List of entity dicts with 'text', 'confidence', 'source'
    """
    if not query or not query.strip():
        return []

    entities = []
    seen = set()

    # Extract acronyms (highest confidence)
    for match in ACRONYM_PATTERN.finditer(query):
        text = match.group().replace(".", "")
        if len(text) >= 2 and text.lower() not in STOPWORDS:
            normalized = text.lower()
            if normalized not in seen:
                seen.add(normalized)
                entities.append({"text": text, "confidence": 0.9, "source": "rule", "type": "acronym"})

    # Extract technical terms with numbers/hyphens
    for match in TECHNICAL_TERM_PATTERN.finditer(query):
        text = match.group()
        if len(text) >= 3 and text.lower() not in STOPWORDS and ("-" in text or any(c.isdigit() for c in text)):
            normalized = text.lower()
            if normalized not in seen:
                seen.add(normalized)
                entities.append({"text": text, "confidence": 0.85, "source": "rule", "type": "technical"})

    # Extract capitalized entities (proper nouns)
    for match in CAPITALIZED_PATTERN.finditer(query):
        text = match.group()
        words = text.split()
        # Skip single common words
        if len(words) == 1 and text.lower() in STOPWORDS:
            continue
        normalized = text.lower()
        if normalized not in seen:
            seen.add(normalized)
            entities.append({"text": text, "confidence": 0.75, "source": "rule", "type": "proper_noun"})

    # Extract Chinese terms
    for match in CHINESE_TERM_PATTERN.finditer(query):
        text = match.group()
        if len(text) >= 2:
            normalized = text.lower()
            if normalized not in seen:
                seen.add(normalized)
                entities.append({"text": text, "confidence": 0.8, "source": "rule", "type": "chinese"})

    # Extract technical phrases
    for match in TECHNICAL_PHRASE_PATTERN.finditer(query):
        text = match.group()
        if len(text) >= 4 and text.lower() not in STOPWORDS:
            normalized = text.lower()
            if normalized not in seen:
                seen.add(normalized)
                entities.append({"text": text, "confidence": 0.7, "source": "rule", "type": "technical_phrase"})

    # Sort by confidence
    entities.sort(key=lambda x: x["confidence"], reverse=True)

    return entities


def _call_llm_for_entities(query: str, max_entities: int) -> list[dict[str, Any]]:
    """
    Internal function to call LLM for entity extraction.

    Args:
        query: Input query
        max_entities: Maximum number of entities to extract

    Returns:
        List of entity dicts
    """
    from app.services.models.runtime import get_chat_model

    try:
        model = get_chat_model(temperature=0.1)

        prompt = f"""Extract the most important named entities, concepts, and technical terms from this query.
Return ONLY a JSON list of entities with their confidence scores (0.0-1.0).

Query: {query}

Format:
[
  {{"text": "entity name", "confidence": 0.95}},
  {{"text": "another entity", "confidence": 0.85}}
]

Extract up to {max_entities} entities. Focus on:
- Named entities (people, organizations, products)
- Technical terms and concepts
- Domain-specific terminology
- Key nouns and noun phrases

Return ONLY the JSON array, no other text."""

        response = model.invoke(prompt)

        # Parse JSON response
        import json

        # Extract content from response
        if hasattr(response, "content"):
            text = response.content.strip()
        else:
            text = str(response).strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            entities = json.loads(text)
            if isinstance(entities, list):
                # Validate structure
                validated = []
                for entity in entities[:max_entities]:
                    if isinstance(entity, dict) and "text" in entity:
                        confidence = float(entity.get("confidence", 0.7))
                        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                        validated.append(
                            {
                                "text": str(entity["text"]).strip(),
                                "confidence": confidence,
                                "source": "llm",
                            }
                        )
                return validated
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response as JSON: %s", e)
            return []

    except Exception as e:
        logger.warning("LLM entity extraction failed: %s", e)
        return []

    return []


def extract_entities_llm(query: str, max_entities: int = 5) -> list[dict[str, Any]]:
    """
    Stage 2: Extract entities using LLM for complex cases.

    Args:
        query: Input query string
        max_entities: Maximum number of entities to extract

    Returns:
        List of entity dicts with 'text', 'confidence', 'source'
    """
    if not query or not query.strip():
        return []

    try:
        return _call_llm_for_entities(query, max_entities)
    except Exception as e:
        logger.warning("LLM entity extraction failed: %s", e)
        return []


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def fuzzy_match_entity(entity: str, candidates: list[str], max_distance: int = 2) -> dict[str, Any] | None:
    """
    Find the best fuzzy match for an entity in a list of candidates.

    Args:
        entity: Entity to match
        candidates: List of candidate entities
        max_distance: Maximum Levenshtein distance (default: 2)

    Returns:
        Dict with 'matched' entity and 'distance', or None if no match
    """
    if not entity or not candidates:
        return None

    entity_lower = entity.lower().strip()
    best_match = None
    best_distance = max_distance + 1

    for candidate in candidates:
        candidate_lower = candidate.lower().strip()

        # Exact match (case-insensitive)
        if entity_lower == candidate_lower:
            return {"matched": candidate, "distance": 0}

        # Calculate Levenshtein distance
        distance = levenshtein_distance(entity_lower, candidate_lower)
        if distance <= max_distance and distance < best_distance:
            best_distance = distance
            best_match = candidate

    if best_match is not None:
        return {"matched": best_match, "distance": best_distance}

    return None


def cross_validate_entities(
    rule_entities: list[dict[str, Any]],
    llm_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Cross-validate entities from both extraction methods.

    Entities that appear in both get confidence boost.
    Uses fuzzy matching for entity linking.

    Args:
        rule_entities: Entities from rule-based extraction
        llm_entities: Entities from LLM extraction

    Returns:
        Validated and deduplicated entity list
    """
    # Build maps for deduplication
    entity_map: dict[str, dict[str, Any]] = {}

    # Add LLM entities first (higher base quality)
    for entity in llm_entities:
        text = entity["text"].strip()
        text_lower = text.lower()
        if text_lower not in entity_map:
            entity_map[text_lower] = {
                "text": text,
                "confidence": entity["confidence"],
                "source": entity["source"],
                "validated_by_both": False,
            }

    # Process rule-based entities
    rule_texts = [e["text"] for e in rule_entities]
    llm_texts = [e["text"] for e in llm_entities]

    for entity in rule_entities:
        text = entity["text"].strip()
        text_lower = text.lower()

        # Check if already exists (exact match)
        if text_lower in entity_map:
            # Boost confidence and mark as validated
            existing = entity_map[text_lower]
            existing["confidence"] = min(1.0, existing["confidence"] * 1.15)
            existing["validated_by_both"] = True
            continue

        # Try fuzzy matching with LLM entities
        fuzzy_result = fuzzy_match_entity(text, llm_texts, max_distance=2)
        if fuzzy_result:
            matched_text = fuzzy_result["matched"]
            matched_lower = matched_text.lower()
            if matched_lower in entity_map:
                # Boost confidence and mark as validated
                existing = entity_map[matched_lower]
                existing["confidence"] = min(1.0, existing["confidence"] * 1.15)
                existing["validated_by_both"] = True
                continue

        # No match found, add as new entity
        entity_map[text_lower] = {
            "text": text,
            "confidence": entity["confidence"],
            "source": entity["source"],
            "validated_by_both": False,
        }

    # Convert back to list and sort by confidence
    validated = list(entity_map.values())
    validated.sort(key=lambda x: x["confidence"], reverse=True)

    return validated


def normalize_for_graph(entity_text: str) -> str:
    """
    Normalize entity text for graph lookup.

    Applies entity aliases and normalization.

    Args:
        entity_text: Raw entity text

    Returns:
        Normalized entity text
    """
    text_lower = entity_text.lower().strip()

    # Remove dots from acronyms for matching: "A.I." -> "ai"
    text_no_dots = text_lower.replace(".", "")

    # Apply aliases (check both original and dot-removed versions)
    if text_lower in _ENTITY_ALIASES:
        return _ENTITY_ALIASES[text_lower]
    if text_no_dots in _ENTITY_ALIASES:
        return _ENTITY_ALIASES[text_no_dots]

    # Try removing trailing 's' for plural matching
    if text_no_dots.endswith('s') and len(text_no_dots) > 2:
        text_singular = text_no_dots[:-1]
        if text_singular in _ENTITY_ALIASES:
            return _ENTITY_ALIASES[text_singular]

    # Normalize using existing utility
    normalized = normalize_string(text_lower, lowercase=True)

    return normalized or text_lower


def extract_entities(
    query: str,
    use_llm: bool = True,
    max_entities: int = 8,
) -> list[dict[str, Any]]:
    """
    Multi-stage entity extraction with validation.

    Combines rule-based and LLM-based extraction with cross-validation.

    Args:
        query: Input query string
        use_llm: Whether to use LLM extraction (default: True)
        max_entities: Maximum number of entities to return

    Returns:
        List of validated entity dicts sorted by confidence
    """
    if not query or not query.strip():
        return []

    # Stage 1: Rule-based extraction
    rule_entities = extract_entities_rule_based(query)

    if not use_llm:
        # Return rule-based entities only
        return rule_entities[:max_entities]

    # Stage 2: LLM-based extraction
    llm_entities = extract_entities_llm(query, max_entities=max_entities)

    # Stage 3: Cross-validation
    if rule_entities and llm_entities:
        validated = cross_validate_entities(rule_entities, llm_entities)
    elif llm_entities:
        validated = llm_entities
    else:
        validated = rule_entities

    # Apply normalization and deduplication
    normalized_map: dict[str, dict[str, Any]] = {}
    for entity in validated:
        normalized = normalize_for_graph(entity["text"])
        if normalized not in normalized_map:
            normalized_map[normalized] = entity

    final_entities = list(normalized_map.values())

    # Sort by confidence and limit
    final_entities.sort(key=lambda x: x["confidence"], reverse=True)

    return final_entities[:max_entities]

