"""
Unified Entity Extraction Service (P2-7).

Centralized entity extraction to avoid code duplication across agents.
"""

import logging
import re

logger = logging.getLogger(__name__)


def extract_entities(
    text: str,
    max_entities: int = 10,
    min_entity_length: int = 2,
    max_entity_length: int = 50,
) -> list[str]:
    """
    Extract named entities from text using pattern matching.

    This is a lightweight extraction method suitable for real-time processing.
    For production, consider using spaCy or a dedicated NER model.

    Args:
        text: Text to extract entities from
        max_entities: Maximum number of entities to return
        min_entity_length: Minimum entity length (characters)
        max_entity_length: Maximum entity length (characters)

    Returns:
        List of extracted entity strings, sorted by frequency/length
    """
    if not text or not text.strip():
        return []

    entities: set[str] = set()

    # 1. Extract Chinese entities (2+ consecutive Chinese characters)
    chinese_pattern = r"[一-鿿]{2,}"
    chinese_matches = re.findall(chinese_pattern, text)
    for match in chinese_matches:
        if min_entity_length <= len(match) <= max_entity_length:
            # Filter out common stop words
            if match not in {"这个", "那个", "什么", "怎么", "如何", "可以", "应该"}:
                entities.add(match)

    # 2. Extract English entities (capitalized words)
    english_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
    english_matches = re.findall(english_pattern, text)
    for match in english_matches:
        if min_entity_length <= len(match) <= max_entity_length:
            # Filter out common words
            if match not in {"The", "This", "That", "What", "How", "Can", "Should"}:
                entities.add(match)

    # 3. Extract acronyms (2-6 uppercase letters)
    acronym_pattern = r"\b[A-Z]{2,6}\b"
    acronym_matches = re.findall(acronym_pattern, text)
    for match in acronym_matches:
        entities.add(match)

    # 4. Extract numbers with context (e.g., "2024年", "95%")
    number_context_pattern = r"\d+(?:\.\d+)?[年月日%]"
    number_matches = re.findall(number_context_pattern, text)
    for match in number_matches:
        entities.add(match)

    # Convert to list and sort by length (longer entities first)
    entity_list = list(entities)
    entity_list.sort(key=lambda x: len(x), reverse=True)

    # Return top N
    result = entity_list[:max_entities]

    logger.debug(f"Extracted {len(result)} entities from text: {result}")
    return result


def extract_entities_with_frequency(
    text: str,
    max_entities: int = 10,
) -> list[tuple[str, int]]:
    """
    Extract entities with their frequency counts.

    Args:
        text: Text to extract entities from
        max_entities: Maximum number of entities to return

    Returns:
        List of (entity, count) tuples, sorted by count descending
    """
    if not text or not text.strip():
        return []

    # Get all entities (duplicates allowed)
    all_entities = []

    # Chinese entities
    chinese_matches = re.findall(r"[一-鿿]{2,}", text)
    all_entities.extend([m for m in chinese_matches if m not in {"这个", "那个", "什么"}])

    # English entities
    english_matches = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
    all_entities.extend([m for m in english_matches if m not in {"The", "This", "That"}])

    # Count frequencies
    from collections import Counter

    entity_counts = Counter(all_entities)

    # Return top N by frequency
    result = entity_counts.most_common(max_entities)

    logger.debug(f"Extracted {len(result)} entities with frequency: {result}")
    return result


def merge_entity_lists(*entity_lists: list[str]) -> list[str]:
    """
    Merge multiple entity lists, removing duplicates and sorting by length.

    Args:
        *entity_lists: Variable number of entity lists to merge

    Returns:
        Merged and deduplicated list of entities
    """
    all_entities = set()

    for entity_list in entity_lists:
        all_entities.update(entity_list)

    # Sort by length (longer first)
    result = sorted(all_entities, key=len, reverse=True)

    return result


# Example usage for different agents:
#
# 1. Enhanced RAG Workflow:
#    entities = extract_entities(query + " " + answer)
#
# 2. Context Tracker:
#    entities = extract_entities(query)
#
# 3. With frequency tracking:
#    entity_freq = extract_entities_with_frequency(conversation_history)
