"""Coreference resolution - resolve pronouns to their referents."""

import re


def simple_coreference_resolution(text: str) -> str:
    """
    Simple rule-based coreference resolution.

    Resolves common pronouns (it, they, this, that) to their likely referents.

    Args:
        text: Input text

    Returns:
        Text with pronouns resolved
    """
    sentences = split_into_sentences(text)
    resolved_sentences = []
    recent_entities = []  # Track recent entities

    for sentence in sentences:
        # Extract entities from current sentence
        entities = extract_entities(sentence)
        recent_entities.extend(entities)
        # Keep only last 5 entities
        recent_entities = recent_entities[-5:]

        # Resolve pronouns
        resolved = resolve_pronouns_in_sentence(sentence, recent_entities)
        resolved_sentences.append(resolved)

    return " ".join(resolved_sentences)


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Simple sentence splitting
    sentences = re.split(r"[.!?]+\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def extract_entities(sentence: str) -> list[str]:
    """
    Extract potential entities (nouns) from sentence.

    Args:
        sentence: Input sentence

    Returns:
        List of entity strings
    """
    # Simple pattern: capitalized words or common nouns
    # Pattern: words starting with capital letter
    capitalized = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", sentence)

    # Pattern: technical terms (CamelCase, acronyms)
    technical = re.findall(r"\b[A-Z]{2,}\b|\b[A-Z][a-z]+[A-Z][a-z]+\b", sentence)

    # Common nouns (simplified)
    common_nouns = re.findall(
        r"\b(system|database|model|application|service|framework|library|tool|method|function|class|module)\b",
        sentence,
        re.IGNORECASE,
    )

    entities = capitalized + technical + common_nouns
    # Remove duplicates while preserving order
    seen = set()
    unique_entities = []
    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            unique_entities.append(e)

    return unique_entities


def resolve_pronouns_in_sentence(sentence: str, recent_entities: list[str]) -> str:
    """
    Resolve pronouns in a sentence using recent entities.

    Args:
        sentence: Input sentence
        recent_entities: List of recently mentioned entities

    Returns:
        Sentence with pronouns resolved
    """
    if not recent_entities:
        return sentence

    resolved = sentence

    # Get most recent entity
    most_recent = recent_entities[-1] if recent_entities else None

    # Resolve "it"
    if most_recent:
        # Pattern: "It is", "it was", "it has", etc.
        resolved = re.sub(r"\bIt\b", most_recent, resolved, count=1)
        resolved = re.sub(r"\bit\b", most_recent.lower(), resolved, count=1)

    # Resolve "this" and "that"
    if most_recent:
        resolved = re.sub(r"\bThis\b(?=\s+(?:is|was|has|can|will))", most_recent, resolved, count=1)
        resolved = re.sub(r"\bThat\b(?=\s+(?:is|was|has|can|will))", most_recent, resolved, count=1)

    # Resolve "they" (use plural form if available)
    if len(recent_entities) >= 2:
        plural_ref = f"{recent_entities[-2]} and {recent_entities[-1]}"
        resolved = re.sub(r"\bThey\b", plural_ref, resolved, count=1)

    return resolved


def add_entity_context(text: str) -> str:
    """
    Add entity context annotations to text.

    Args:
        text: Input text

    Returns:
        Text with entity context annotations
    """
    sentences = split_into_sentences(text)
    annotated = []
    entity_stack = []

    for sentence in sentences:
        entities = extract_entities(sentence)

        # Add new entities to stack
        for entity in entities:
            if entity not in entity_stack:
                entity_stack.append(entity)
                # Keep stack size manageable
                if len(entity_stack) > 10:
                    entity_stack.pop(0)

        # Annotate sentence with context
        if entity_stack:
            context = f"[Context: {', '.join(entity_stack[-3:])}] "
            annotated.append(context + sentence)
        else:
            annotated.append(sentence)

    return " ".join(annotated)


def resolve_demonstratives(text: str) -> str:
    """
    Resolve demonstrative pronouns (this, that, these, those).

    Args:
        text: Input text

    Returns:
        Text with demonstratives resolved
    """
    # Pattern: "this/that + noun" - keep as is
    # Pattern: "this/that" alone - try to resolve

    resolved = text

    # Find standalone demonstratives
    patterns = [
        (r"\bthis\s+(?:is|was|has|can|will|should|would)\b", "this concept"),
        (r"\bthat\s+(?:is|was|has|can|will|should|would)\b", "that approach"),
        (r"\bthese\s+(?:are|were|have|can|will|should|would)\b", "these methods"),
        (r"\bthose\s+(?:are|were|have|can|will|should|would)\b", "those techniques"),
    ]

    for pattern, replacement in patterns:
        resolved = re.sub(pattern, replacement, resolved, flags=re.IGNORECASE)

    return resolved
