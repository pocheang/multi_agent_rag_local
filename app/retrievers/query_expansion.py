"""
Query expansion module for improving retrieval through entity extraction and synonym expansion.

Enhances query understanding by:
1. Extracting key entities and technical terms
2. Expanding acronyms and abbreviations
3. Adding synonyms for common terms
"""

import logging
import re

logger = logging.getLogger(__name__)

# Synonym dictionary for common technical terms
# Maps abbreviations and terms to their expanded forms
SYNONYM_DICT = {
    # Machine Learning & AI
    "ml": ["machine learning"],
    "ai": ["artificial intelligence"],
    "nlp": ["natural language processing"],
    "dl": ["deep learning"],
    "nn": ["neural network"],
    "cv": ["computer vision"],
    "rl": ["reinforcement learning"],
    "gan": ["generative adversarial network"],
    "cnn": ["convolutional neural network"],
    "rnn": ["recurrent neural network"],
    "lstm": ["long short-term memory"],
    "gpt": ["generative pre-trained transformer"],
    "bert": ["bidirectional encoder representations from transformers"],
    "llm": ["large language model"],
    # Data Science
    "ds": ["data science"],
    "eda": ["exploratory data analysis"],
    "etl": ["extract transform load"],
    "knn": ["k-nearest neighbors"],
    "svm": ["support vector machine"],
    "pca": ["principal component analysis"],
    "rf": ["random forest"],
    # Software Engineering
    "api": ["application programming interface"],
    "sdk": ["software development kit"],
    "ide": ["integrated development environment"],
    "ci": ["continuous integration"],
    "cd": ["continuous deployment", "continuous delivery"],
    "orm": ["object relational mapping"],
    "crud": ["create read update delete"],
    "rest": ["representational state transfer"],
    "sql": ["structured query language"],
    "nosql": ["not only sql"],
    # Cloud & Infrastructure
    "aws": ["amazon web services"],
    "gcp": ["google cloud platform"],
    "vm": ["virtual machine"],
    "k8s": ["kubernetes"],
    "docker": ["containerization"],
    # Chinese terms (bidirectional mapping)
    "机器学习": ["ML", "machine learning"],
    "人工智能": ["AI", "artificial intelligence"],
    "深度学习": ["DL", "deep learning"],
    "神经网络": ["neural network", "NN"],
    "自然语言处理": ["NLP", "natural language processing"],
}

# Regex patterns for entity extraction
# Matches uppercase acronyms (2-6 chars) and technical terms
ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")
TECHNICAL_TERM_PATTERN = re.compile(r"\b(?:[a-z]+[A-Z][a-z]*)+\b")  # camelCase
COMPOUND_TERM_PATTERN = re.compile(
    r"\b(?:machine learning|deep learning|neural network|"
    r"natural language|computer vision|data science|"
    r"artificial intelligence)\b",
    re.IGNORECASE,
)

# Chinese technical terms
CHINESE_TECH_PATTERN = re.compile(
    r"(?:机器学习|深度学习|人工智能|神经网络|"
    r"自然语言处理|计算机视觉|数据科学)"
)


def extract_entities(query: str) -> list[str]:
    """
    Extract entities and technical terms from query.

    Args:
        query: Input query string

    Returns:
        List of extracted entities (acronyms, technical terms, compounds)
    """
    if not query or not query.strip():
        return []

    entities = []
    query_str = query.strip()

    # Extract acronyms (ML, AI, NLP, etc.)
    acronyms = ACRONYM_PATTERN.findall(query_str)
    entities.extend(acronyms)

    # Extract compound technical terms
    compounds = COMPOUND_TERM_PATTERN.findall(query_str)
    entities.extend(compounds)

    # Extract camelCase terms
    camel_terms = TECHNICAL_TERM_PATTERN.findall(query_str)
    entities.extend(camel_terms)

    # Extract Chinese technical terms
    chinese_terms = CHINESE_TECH_PATTERN.findall(query_str)
    entities.extend(chinese_terms)

    # Deduplicate while preserving order
    seen = set()
    unique_entities = []
    for entity in entities:
        entity_lower = entity.lower()
        if entity_lower not in seen:
            seen.add(entity_lower)
            unique_entities.append(entity)

    return unique_entities


def get_synonyms(term: str) -> list[str]:
    """
    Get synonyms for a given term from the synonym dictionary.

    Args:
        term: Term to look up

    Returns:
        List of synonyms (empty if term not in dictionary)
    """
    if not term or not term.strip():
        return []

    # Normalize term for lookup (lowercase)
    term_lower = term.strip().lower()

    # Direct lookup
    if term_lower in SYNONYM_DICT:
        return SYNONYM_DICT[term_lower].copy()

    # Also check original case for Chinese terms
    if term.strip() in SYNONYM_DICT:
        return SYNONYM_DICT[term.strip()].copy()

    return []


def expand_query(query: str, max_expansion_ratio: float = 3.0) -> str:
    """
    Expand query with entities and their synonyms.

    Args:
        query: Original query string
        max_expansion_ratio: Maximum expansion ratio to prevent explosion (default: 3.0)

    Returns:
        Expanded query string with original query + synonyms
    """
    if not query or not query.strip():
        return ""

    query_str = query.strip()

    # Extract entities from the query
    entities = extract_entities(query_str)

    if not entities:
        # No entities found, return original
        return query_str

    # Collect synonyms for all entities
    expansions = []
    seen_expansions = set()

    for entity in entities:
        synonyms = get_synonyms(entity)

        for synonym in synonyms:
            synonym_lower = synonym.lower()
            # Avoid adding if already in original query or already added
            if synonym_lower not in query_str.lower() and synonym_lower not in seen_expansions:
                expansions.append(synonym)
                seen_expansions.add(synonym_lower)

    # Build expanded query
    if not expansions:
        # No new expansions found
        return query_str

    # Combine original query with expansions
    expanded = f"{query_str} {' '.join(expansions)}"

    # Check expansion ratio to prevent explosion
    if len(expanded) > len(query_str) * max_expansion_ratio:
        # Too much expansion, limit to first few synonyms
        limited_expansions = expansions[: min(3, len(expansions))]
        expanded = f"{query_str} {' '.join(limited_expansions)}"
        logger.debug(f"Limited expansion from {len(expansions)} to {len(limited_expansions)} synonyms")

    return expanded
