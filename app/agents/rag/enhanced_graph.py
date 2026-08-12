"""
PDF-aware Graph RAG integration module.

This module bridges PDF processing and Graph RAG to improve accuracy by:
1. Extracting document quality signals from PDFs
2. Applying adaptive graph lookup parameters
3. Enriching graph queries with PDF-derived context
"""

import logging

from app.agents.rag.cache import (
    cached_document_context,
    cached_entity_extraction,
    cached_pdf_quality,
)
from app.agents.rag.config import (
    CHINESE_NOISE_PATTERNS,
    CHINESE_NOISE_TERMS,
    CHINESE_SUFFIX_NOISE,
    CHINESE_TERM_KEYWORDS,
    DEFAULT_ENTITY_LIMIT,
    DEFAULT_TOP_K_DOCS,
    DENSITY_ACCEPTABLE_MAX,
    DENSITY_ACCEPTABLE_MIN,
    DENSITY_OPTIMAL_MAX,
    DENSITY_OPTIMAL_MIN,
    ENGLISH_NOISE_TERMS,
    ENGLISH_SINGLE_TERM_KEYWORDS,
    GRAPH_PARAMS_HIGH_QUALITY,
    GRAPH_PARAMS_LOW_QUALITY,
    GRAPH_PARAMS_MEDIUM_QUALITY,
    MAX_ENTITY_LENGTH,
    MAX_ENTITY_WORDS,
    MIN_ENTITIES_FOR_HIGH_CONFIDENCE,
    MIN_ENTITIES_FOR_MEDIUM_CONFIDENCE,
    MIN_ENTITY_LENGTH,
    PAGE_COUNT_HIGH,
    PAGE_COUNT_MEDIUM,
    PATTERN_ACRONYMS,
    PATTERN_CAMEL_CASE,
    PATTERN_CHINESE_TERMS,
    PATTERN_HEADERS,
    PATTERN_LISTS,
    PATTERN_PROPER_NOUNS,
    PATTERN_QUERY_ENTITIES,
    PATTERN_REFERENCES,
    PATTERN_RELATION_KEYWORDS,
    PATTERN_TABLES,
    PATTERN_TECH_TERMS,
    PATTERN_TECHNICAL_PHRASES_EN,
    PATTERN_TECHNICAL_PHRASES_ZH,
    QUALITY_THRESHOLD_HIGH,
    QUALITY_THRESHOLD_LOW,
    QUALITY_WEIGHT_CONTENT,
    QUALITY_WEIGHT_METADATA,
    QUALITY_WEIGHT_STRUCTURE,
    TECH_TERM_COUNT_HIGH,
    TECH_TERM_COUNT_MEDIUM,
    WORD_COUNT_HIGH,
    WORD_COUNT_MEDIUM,
)
from app.tools.graph_tools_enhanced import graph_lookup_enhanced

logger = logging.getLogger(__name__)


__all__ = [
    "analyze_pdf_quality",
    "extract_document_entities",
    "get_document_context_for_query",
    "run_graph_rag_with_pdf_context",
    "should_use_graph_rag",
]


def _is_english_entity_candidate(term: str) -> bool:
    """
    Check if an English term is a valid entity candidate.

    Args:
        term: Term to check

    Returns:
        True if valid entity candidate
    """
    normalized = " ".join(term.split()).strip()
    if len(normalized) < MIN_ENTITY_LENGTH:
        return False

    lowered = normalized.lower()
    if lowered in ENGLISH_NOISE_TERMS:
        return False

    words = normalized.split()
    if len(words) > MAX_ENTITY_WORDS:
        return False

    if len(words) == 1:
        if normalized.isupper():
            return True
        return any(keyword in lowered for keyword in ENGLISH_SINGLE_TERM_KEYWORDS)

    return True


def _is_chinese_entity_candidate(term: str) -> bool:
    """
    Check if a Chinese term is a valid entity candidate.

    Args:
        term: Term to check

    Returns:
        True if valid entity candidate
    """
    normalized = term.strip()
    if not normalized or len(normalized) < MIN_ENTITY_LENGTH or len(normalized) > MAX_ENTITY_LENGTH:
        return False

    if normalized in CHINESE_NOISE_TERMS:
        return False

    if any(marker in normalized for marker in CHINESE_NOISE_PATTERNS):
        return False

    if normalized.endswith(CHINESE_SUFFIX_NOISE):
        return False

    return any(keyword in normalized for keyword in CHINESE_TERM_KEYWORDS)


def _append_unique_entity(
    entities: list[str],
    seen: set[str],
    term: str,
    limit: int,
) -> None:
    """
    Append entity to list if unique and under limit.

    Args:
        entities: List to append to
        seen: Set of seen entities (case-insensitive)
        term: Entity term to add
        limit: Maximum list size
    """
    normalized = " ".join(term.split()).strip(" ,.;:()[]{}<>-_")
    if not normalized:
        return

    key = normalized.casefold()
    if key in seen:
        return

    seen.add(key)
    if len(entities) < limit:
        entities.append(normalized)


@cached_pdf_quality
def analyze_pdf_quality(text: str, metadata: dict) -> float:
    """
    Analyze PDF content quality for graph extraction confidence.

    Quality indicators:
    - Clear structure (headers, sections)
    - Formatted content (tables, lists)
    - Reasonable density (not too sparse/dense)
    - Presence of key sections (references, index)

    Args:
        text: Extracted PDF text
        metadata: PDF metadata (pages, format, etc.)

    Returns:
        Quality score (0-1)
    """
    score = 0.0

    # Structure score (40%)
    structure_score = 0.0
    if PATTERN_HEADERS.search(text):
        structure_score += 0.15
    if PATTERN_TABLES.search(text):
        structure_score += 0.10
    if PATTERN_LISTS.search(text):
        structure_score += 0.10
    if PATTERN_REFERENCES.search(text):
        structure_score += 0.05
    score += min(QUALITY_WEIGHT_STRUCTURE, structure_score)

    # Content score (40%)
    content_score = 0.0
    words = text.split()
    word_count = len(words)
    char_count = len(text)

    if char_count > 0:
        density = word_count / (char_count / 100)
        if DENSITY_OPTIMAL_MIN <= density <= DENSITY_OPTIMAL_MAX:
            content_score += 0.15
        elif DENSITY_ACCEPTABLE_MIN <= density <= DENSITY_ACCEPTABLE_MAX:
            content_score += 0.08

    if word_count >= WORD_COUNT_HIGH:
        content_score += 0.15
    elif word_count >= WORD_COUNT_MEDIUM:
        content_score += 0.08

    tech_terms = len(PATTERN_TECH_TERMS.findall(text))
    if tech_terms >= TECH_TERM_COUNT_HIGH:
        content_score += 0.10
    elif tech_terms >= TECH_TERM_COUNT_MEDIUM:
        content_score += 0.05
    score += min(QUALITY_WEIGHT_CONTENT, content_score)

    # Metadata score (20%)
    metadata_score = 0.0
    page_count = metadata.get("page", 0) if isinstance(metadata.get("page"), int) else 1
    total_pages = metadata.get("total_pages", page_count)
    if total_pages >= PAGE_COUNT_HIGH:
        metadata_score += 0.10
    elif total_pages >= PAGE_COUNT_MEDIUM:
        metadata_score += 0.05
    if metadata.get("format") == "markdown":
        metadata_score += 0.05
    if metadata.get("enhanced") or metadata.get("converter") == "docling":
        metadata_score += 0.05
    score += min(QUALITY_WEIGHT_METADATA, metadata_score)

    return min(1.0, score)


@cached_entity_extraction
def extract_document_entities(text: str, limit: int = DEFAULT_ENTITY_LIMIT) -> list[str]:
    """
    Extract potential entities from document text for query enrichment.

    Args:
        text: Document text
        limit: Maximum entities to extract

    Returns:
        List of entity strings
    """
    entities: list[str] = []
    seen: set[str] = set()

    # Extract technical phrases (English)
    for term in PATTERN_TECHNICAL_PHRASES_EN.findall(text):
        _append_unique_entity(entities, seen, term.title(), limit)

    # Extract proper nouns
    for term in PATTERN_PROPER_NOUNS.findall(text):
        if _is_english_entity_candidate(term):
            _append_unique_entity(entities, seen, term, limit)

    # Extract acronyms
    for term in PATTERN_ACRONYMS.findall(text):
        _append_unique_entity(entities, seen, term, limit)

    # Extract CamelCase terms
    for term in PATTERN_CAMEL_CASE.findall(text):
        _append_unique_entity(entities, seen, term, limit)

    # Extract technical phrases (Chinese)
    for term in PATTERN_TECHNICAL_PHRASES_ZH.findall(text):
        _append_unique_entity(entities, seen, term, limit)

    # Extract Chinese technical terms
    for term in PATTERN_CHINESE_TERMS.findall(text):
        if _is_chinese_entity_candidate(term):
            _append_unique_entity(entities, seen, term, limit)

    return entities[:limit]


@cached_document_context
def get_document_context_for_query(
    question: str,
    retrieved_docs: list[dict],
    top_k: int = DEFAULT_TOP_K_DOCS,
) -> dict:
    """
    Analyze retrieved documents to build context for graph queries.

    Args:
        question: User query
        retrieved_docs: List of retrieved documents with content and metadata
        top_k: Number of top documents to analyze

    Returns:
        Context dictionary with quality scores and enrichment data
    """
    if not retrieved_docs:
        return {
            "quality_score": 0.5,
            "entities": [],
            "confidence": "low",
        }

    quality_scores = []
    all_entities = set()

    for doc in retrieved_docs[:top_k]:
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})
        quality_scores.append(analyze_pdf_quality(content, metadata))
        all_entities.update(extract_document_entities(content, limit=10))

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

    # Determine confidence level
    if avg_quality >= QUALITY_THRESHOLD_HIGH and len(all_entities) >= MIN_ENTITIES_FOR_HIGH_CONFIDENCE:
        confidence = "high"
    elif avg_quality >= 0.5 or len(all_entities) >= MIN_ENTITIES_FOR_MEDIUM_CONFIDENCE:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "quality_score": avg_quality,
        "entities": list(all_entities)[:15],
        "document_count": len(retrieved_docs[:top_k]),
        "confidence": confidence,
    }


def run_graph_rag_with_pdf_context(
    question: str,
    retrieved_docs: list[dict] | None = None,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
) -> dict:
    """
    Enhanced Graph RAG with PDF-aware optimizations.

    This is a drop-in replacement for run_graph_rag that applies
    PDF quality analysis and adaptive parameters.

    Args:
        question: User query
        retrieved_docs: Retrieved documents (for quality analysis)
        allowed_sources: Optional source filter
        agent_class: Agent class for document filtering

    Returns:
        Graph RAG results with enhanced accuracy
    """
    from app.services.agent_document_filter import get_sources_by_agent_class

    if allowed_sources is None and agent_class:
        allowed_sources = get_sources_by_agent_class(agent_class)

    # Analyze document context
    if retrieved_docs:
        context = get_document_context_for_query(question, retrieved_docs)
        context_quality = context["quality_score"]
        logger.info(
            "PDF context analysis: quality=%.2f, entities=%s, confidence=%s",
            context_quality,
            len(context["entities"]),
            context["confidence"],
        )
    else:
        context_quality = 0.5
        context = {"quality_score": 0.5, "entities": [], "confidence": "medium"}

    # Select adaptive parameters based on quality
    if context_quality >= QUALITY_THRESHOLD_HIGH:
        params = GRAPH_PARAMS_HIGH_QUALITY
    elif context_quality >= 0.5:
        params = GRAPH_PARAMS_MEDIUM_QUALITY
    else:
        params = GRAPH_PARAMS_LOW_QUALITY

    try:
        graph_result = graph_lookup_enhanced(
            question=question,
            allowed_sources=allowed_sources,
            context_quality=context_quality,
            max_entities=params["max_entities"],
            max_neighbors=params["max_neighbors"],
            max_paths=params["max_paths"],
        )
    except Exception as e:
        error_type = type(e).__name__

        if error_type in {"ServiceUnavailable", "ConnectionError"}:
            logger.warning(
                "Enhanced graph lookup unavailable for question '%s': %s",
                question,
                error_type,
            )
        else:
            logger.exception("Enhanced graph lookup failed for question: %s", question)

        return {
            "context": "",
            "entities": [],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.0,
            "confidence": "low",
            "error": f"graph_lookup_error:{error_type}",
        }

    entities = graph_result.get("entities", [])
    neighbors = graph_result.get("neighbors", [])
    paths = graph_result.get("paths", [])
    graph_signal_score = float(graph_result.get("graph_signal_score", 0.0) or 0.0)
    confidence = graph_result.get("confidence", "medium")

    # Format context string
    lines = []
    for item in entities:
        name = item.get("entity", "")
        if not name:
            continue
        lines.append(f"Entity: {name}")
        for rel in item.get("relations", []):
            if rel.get("other"):
                lines.append(f"  - {rel.get('relation')} ({rel.get('weight', 0):.2f}) -> {rel.get('other')}")

    for row in neighbors:
        if row.get("entity") and row.get("relation") and row.get("other"):
            lines.append(
                f"Neighbor: {row['entity']} -[{row['relation']}|{float(row.get('weight', 0)):.2f}]- {row['other']}"
            )

    for row in paths:
        if row.get("source") and row.get("middle") and row.get("target"):
            lines.append(
                f"Path2Hop: {row['source']} -[{row.get('rel1', '')}]- {row['middle']} "
                f"-[{row.get('rel2', '')}]- {row['target']} | w={float(row.get('weight', 0)):.2f}"
            )

    return {
        "context": "\n".join(lines),
        "entities": [item.get("entity") for item in entities if item.get("entity")],
        "neighbors": neighbors,
        "paths": paths,
        "graph_signal_score": graph_signal_score,
        "confidence": confidence,
        "pdf_context": context,
    }


def should_use_graph_rag(
    question: str,
    retrieved_docs: list[dict] | None = None,
    graph_signal_score: float | None = None,
) -> tuple[bool, str]:
    """
    Decide whether to use Graph RAG based on context.

    Decision factors:
    - Graph signal strength
    - Document quality
    - Query characteristics

    Args:
        question: User query
        retrieved_docs: Retrieved documents
        graph_signal_score: Pre-computed graph signal (if available)

    Returns:
        Tuple of (should_use, reason)
    """
    # Strong graph signal → use
    if graph_signal_score is not None and graph_signal_score >= 0.6:
        return True, f"strong_graph_signal:{graph_signal_score:.2f}"

    # Check document quality
    if retrieved_docs:
        context = get_document_context_for_query(question, retrieved_docs)
        if (
            context["quality_score"] >= QUALITY_THRESHOLD_HIGH
            and len(context["entities"]) >= MIN_ENTITIES_FOR_HIGH_CONFIDENCE
        ):
            return True, "high_quality_documents_with_entities"
        if context["quality_score"] < QUALITY_THRESHOLD_LOW:
            return False, "low_quality_documents"

    # Check query characteristics
    potential_entities = len(PATTERN_QUERY_ENTITIES.findall(question))
    if potential_entities >= 3:
        return True, f"multi_entity_query:{potential_entities}_entities"

    if PATTERN_RELATION_KEYWORDS.search(question):
        return True, "relationship_query"

    return True, "default_strategy"
