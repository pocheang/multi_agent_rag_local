"""
Enhanced Graph Tools for improved PDF + Graph RAG accuracy.

Key improvements:
1. Better entity normalization with cross-language support
2. Adaptive graph signal scoring based on content quality
3. Semantic similarity for entity matching
4. PDF-aware relationship weighting
5. Multi-hop path exploration with relevance ranking

OPTIMIZATIONS:
- Uses centralized configuration from graph_tools_config
- Precompiled regex patterns
- Improved type hints
- Better error handling and logging
"""

import logging
import re

from app.domain.text import normalize_string
from app.graph.knowledge.client import Neo4jClient
from app.services.runtime.bulkhead import bulkhead
from app.services.runtime.resilience import call_with_circuit_breaker
from app.tools.graph.config import (
    CONFIDENCE_HIGH_ENTITIES,
    CONFIDENCE_HIGH_NEIGHBORS,
    CONFIDENCE_HIGH_PATHS,
    CONFIDENCE_HIGH_SIGNAL,
    CONFIDENCE_MEDIUM_ENTITIES,
    CONFIDENCE_MEDIUM_NEIGHBORS,
    CONFIDENCE_MEDIUM_SIGNAL,
    ENTITY_ALIASES,
    ENTITY_COUNT_OPTIMAL,
    ENTITY_RETRIEVAL_MULTIPLIER,
    HIGH_VALUE_RELATIONS,
    NEIGHBOR_QUALITY_BOOST,
    NEIGHBOR_RETRIEVAL_MULTIPLIER,
    NOISY_RELATIONS,
    PATH_RETRIEVAL_MULTIPLIER,
    PATH_WEIGHT_BOOST,
    QUALITY_BOOST_MAX,
    QUALITY_BOOST_THRESHOLD,
    RELATION_WEIGHT_HIGH,
    RELATION_WEIGHT_MEDIUM,
    SIGNAL_WEIGHT_ENTITY,
    SIGNAL_WEIGHT_NEIGHBOR,
    SIGNAL_WEIGHT_PATH,
    TOKEN_PATTERN_STRING,
)

logger = logging.getLogger(__name__)

# Precompiled token pattern
TOKEN_PATTERN = re.compile(TOKEN_PATTERN_STRING)


def _normalize_token(token: str) -> str:
    """
    Normalize a token with alias expansion.

    Args:
        token: Raw token string

    Returns:
        Normalized token (with alias expansion if applicable)
    """
    normalized = normalize_string(token, lowercase=True)
    if not normalized:
        return ""
    return ENTITY_ALIASES.get(normalized, normalized)


def _normalize_entity_name(name: str) -> str:
    """
    Normalize entity name with smart handling of multi-token entities.

    Args:
        name: Entity name to normalize

    Returns:
        Normalized entity name
    """
    # Try full name first for alias match
    normalized_full = _normalize_token(name)
    if normalized_full != normalize_string(name, lowercase=True):
        # Found an alias
        return normalized_full

    # For multi-token names, keep as-is but normalize
    return normalize_string(name, lowercase=True)


def _relation_weight(rel: str, context_quality: float = 0.5) -> float:
    """
    Calculate relation weight with context-aware scoring.

    Args:
        rel: Relationship type
        context_quality: Quality score of source document (0-1)

    Returns:
        Weight score (0-1)
    """
    normalized = normalize_string(rel, lowercase=True)
    if not normalized:
        return 0.0

    # Filter noise
    if normalized in NOISY_RELATIONS:
        return 0.0

    # Determine base weight
    if any(keyword in normalized for keyword in HIGH_VALUE_RELATIONS):
        base_weight = RELATION_WEIGHT_HIGH
    else:
        base_weight = RELATION_WEIGHT_MEDIUM

    # Apply context quality boost
    # High-quality PDFs with good structure → higher confidence in relations
    if context_quality >= QUALITY_BOOST_THRESHOLD:
        quality_boost = 1.0 + QUALITY_BOOST_MAX
    else:
        quality_boost = 1.0 + (context_quality * QUALITY_BOOST_MAX)

    return min(1.0, base_weight * quality_boost)


def _calculate_semantic_similarity(query_tokens: list[str], entity_name: str) -> float:
    """
    Calculate semantic similarity between query tokens and entity.

    Simple approach: token overlap with position weighting.
    For production, consider using embeddings.

    Args:
        query_tokens: Normalized query tokens
        entity_name: Entity name to compare

    Returns:
        Similarity score (0-1)
    """
    entity_tokens = set(TOKEN_PATTERN.findall(entity_name.lower()))
    if not entity_tokens or not query_tokens:
        return 0.0

    # Exact matches
    exact_matches = sum(1 for token in query_tokens if token in entity_tokens)

    # Partial matches (substring)
    partial_matches = sum(
        0.5
        for query_token in query_tokens
        for entity_token in entity_tokens
        if query_token in entity_token or entity_token in query_token
    )

    similarity = (exact_matches + partial_matches) / max(len(query_tokens), len(entity_tokens))
    return min(1.0, similarity)


def graph_lookup_enhanced(
    question: str,
    allowed_sources: list[str] | None = None,
    context_quality: float = 0.5,
    max_entities: int = 10,
    max_neighbors: int = 15,
    max_paths: int = 10,
) -> dict:
    """
    Enhanced graph lookup with better accuracy for PDF content.

    Improvements over basic graph_lookup:
    - Better entity normalization and alias matching
    - Context-aware relation weighting
    - Semantic similarity scoring
    - Adaptive result limits based on confidence

    Args:
        question: User query
        allowed_sources: Optional source filter
        context_quality: Quality score of source documents (0-1)
        max_entities: Maximum entities to retrieve
        max_neighbors: Maximum neighbor relationships
        max_paths: Maximum 2-hop paths

    Returns:
        Dictionary with entities, neighbors, paths, and enhanced scoring
    """
    # Extract and normalize tokens
    raw_tokens = TOKEN_PATTERN.findall(question)
    tokens = [_normalize_token(token) for token in raw_tokens if _normalize_token(token)]

    if not tokens:
        logger.warning(f"No valid tokens extracted from question: {question}")
        return {
            "entities": [],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.0,
            "confidence": "low",
        }

    with bulkhead("neo4j"):
        client = Neo4jClient()
        try:
            # Search entities with higher limit for ranking
            entities = call_with_circuit_breaker(
                "neo4j.search_entities",
                lambda: client.search_entities(
                    tokens, limit=max_entities * ENTITY_RETRIEVAL_MULTIPLIER, allowed_sources=allowed_sources
                ),
            )

            # Normalize and score entities
            scored_entities = []
            lookup_entity_names = []

            for row in entities:
                raw_entity_name = str(row.get("entity", "")).strip()
                entity_name = _normalize_entity_name(raw_entity_name)

                if not entity_name:
                    continue

                # Calculate relevance score
                relevance = _calculate_semantic_similarity(tokens, entity_name)

                # Process relations with context-aware weighting
                normalized_rels = []
                for rel in row.get("relations", []) or []:
                    relation = str(rel.get("relation", "")).strip()
                    other = _normalize_entity_name(str(rel.get("other", "")).strip())
                    weight = _relation_weight(relation, context_quality)

                    if not other or weight <= 0:
                        continue

                    normalized_rels.append(
                        {
                            "relation": relation,
                            "other": other,
                            "weight": weight,
                        }
                    )

                scored_entities.append(
                    {
                        "entity": entity_name,
                        "relations": normalized_rels,
                        "relevance": relevance,
                        "raw_name": raw_entity_name,
                    }
                )

            # Sort by relevance and limit
            scored_entities.sort(key=lambda x: x["relevance"], reverse=True)
            top_entities = scored_entities[:max_entities]

            # Collect names for neighbor and path queries
            for entity_data in top_entities:
                lookup_entity_names.append(entity_data["raw_name"])

            # Retrieve neighbors with deduplication
            neighbor_rows = []
            seen_neighbor: set[tuple[str, str, str]] = set()

            for name in lookup_entity_names[:5]:  # Top 5 entities only
                current_name = name
                rows = call_with_circuit_breaker(
                    "neo4j.entity_neighbors",
                    lambda n=current_name: client.entity_neighbors(
                        n, limit=max_neighbors * NEIGHBOR_RETRIEVAL_MULTIPLIER, allowed_sources=allowed_sources
                    ),
                )

                for row in rows:
                    entity = _normalize_entity_name(str(row.get("entity", "")).strip())
                    relation = str(row.get("relation", "")).strip()
                    other = _normalize_entity_name(str(row.get("other", "")).strip())
                    weight = _relation_weight(relation, context_quality)

                    if not entity or not other or weight <= 0:
                        continue

                    key = (entity, relation.lower(), other)
                    if key in seen_neighbor:
                        continue

                    seen_neighbor.add(key)
                    neighbor_rows.append(
                        {
                            "entity": entity,
                            "relation": relation,
                            "other": other,
                            "weight": weight,
                        }
                    )

            # Sort neighbors by weight and limit
            neighbor_rows.sort(key=lambda x: x["weight"], reverse=True)
            neighbor_rows = neighbor_rows[:max_neighbors]

            # Retrieve 2-hop paths
            path_rows = []
            seen_path: set[tuple[str, str, str, str, str]] = set()

            for name in lookup_entity_names[:3]:  # Top 3 entities for paths
                current_name = name
                paths = call_with_circuit_breaker(
                    "neo4j.entity_paths_2hop",
                    lambda n=current_name: client.entity_paths_2hop(
                        n, limit=max_paths * PATH_RETRIEVAL_MULTIPLIER, allowed_sources=allowed_sources
                    ),
                )

                for path in paths:
                    source = _normalize_entity_name(str(path.get("source", "")).strip())
                    middle = _normalize_entity_name(str(path.get("middle", "")).strip())
                    target = _normalize_entity_name(str(path.get("target", "")).strip())
                    rel1 = str(path.get("rel1", "")).strip()
                    rel2 = str(path.get("rel2", "")).strip()

                    w1 = _relation_weight(rel1, context_quality)
                    w2 = _relation_weight(rel2, context_quality)

                    if not source or not middle or not target or w1 <= 0 or w2 <= 0:
                        continue

                    pkey = (source, rel1.lower(), middle, rel2.lower(), target)
                    if pkey in seen_path:
                        continue

                    seen_path.add(pkey)
                    path_rows.append(
                        {
                            "source": source,
                            "rel1": rel1,
                            "middle": middle,
                            "rel2": rel2,
                            "target": target,
                            "weight": (w1 + w2) / 2.0,
                        }
                    )

            # Sort paths by weight and limit
            path_rows.sort(key=lambda x: x["weight"], reverse=True)
            path_rows = path_rows[:max_paths]

            # Calculate enhanced graph signal score
            graph_signal_score = _calculate_enhanced_signal_score(
                top_entities,
                neighbor_rows,
                path_rows,
                context_quality,
            )

            # Determine confidence level
            confidence = _determine_confidence(
                graph_signal_score,
                len(top_entities),
                len(neighbor_rows),
                len(path_rows),
            )

            # Remove internal scoring fields from output
            clean_entities = [{"entity": entity["entity"], "relations": entity["relations"]} for entity in top_entities]

            return {
                "entities": clean_entities,
                "neighbors": neighbor_rows,
                "paths": path_rows,
                "graph_signal_score": graph_signal_score,
                "confidence": confidence,
                "diagnostics": {
                    "query_tokens": len(tokens),
                    "context_quality": context_quality,
                    "top_entity_relevance": top_entities[0]["relevance"] if top_entities else 0.0,
                },
            }

        except Exception:
            logger.exception("Enhanced graph lookup failed")
            raise
        finally:
            client.close()


def _calculate_enhanced_signal_score(
    entities: list[dict],
    neighbors: list[dict],
    paths: list[dict],
    context_quality: float,
) -> float:
    """
    Calculate enhanced graph signal score with adaptive weighting.

    Args:
        entities: Scored entity list
        neighbors: Neighbor relationships
        paths: 2-hop paths
        context_quality: Document quality score (0-1)

    Returns:
        Enhanced signal score (0-1)
    """
    # Entity score: count + relevance
    if entities:
        count_score = min(1.0, len(entities) / ENTITY_COUNT_OPTIMAL)
        avg_relevance = sum(entity["relevance"] for entity in entities) / len(entities)
        entity_score = (count_score + avg_relevance) / 2.0
    else:
        entity_score = 0.0

    # Neighbor score: weighted average with quality boost
    if neighbors:
        weights = [float(neighbor.get("weight", 0.0)) for neighbor in neighbors]
        neighbor_score = sum(weights) / len(weights)
        # High-quality neighbors from good context get a boost
        if context_quality >= QUALITY_BOOST_THRESHOLD:
            neighbor_score = min(1.0, neighbor_score * NEIGHBOR_QUALITY_BOOST)
    else:
        neighbor_score = 0.0

    # Path score: multi-hop reasoning bonus
    if paths:
        weights = [float(path.get("weight", 0.0)) for path in paths]
        path_score = sum(weights) / len(weights)
        # Multi-hop paths are valuable, give them a boost
        path_score = min(1.0, path_score * PATH_WEIGHT_BOOST)
    else:
        path_score = 0.0

    # Adaptive weighting based on what we found
    components = []
    weights = []

    if entities:
        components.append(entity_score)
        weights.append(SIGNAL_WEIGHT_ENTITY)

    if neighbors:
        components.append(neighbor_score)
        weights.append(SIGNAL_WEIGHT_NEIGHBOR)

    if paths:
        components.append(path_score)
        weights.append(SIGNAL_WEIGHT_PATH)

    if not components:
        return 0.0

    # Normalize weights
    total_weight = sum(weights)
    normalized_weights = [weight / total_weight for weight in weights]

    # Calculate weighted score
    score = sum(component * weight for component, weight in zip(components, normalized_weights, strict=False))

    # Apply context quality multiplier (subtle)
    score = score * (0.9 + context_quality * 0.1)

    return min(1.0, score)


def _determine_confidence(
    signal_score: float,
    entity_count: int,
    neighbor_count: int,
    path_count: int,
) -> str:
    """
    Determine confidence level based on graph coverage.

    Args:
        signal_score: Graph signal score
        entity_count: Number of entities found
        neighbor_count: Number of neighbors found
        path_count: Number of paths found

    Returns:
        Confidence level: "high", "medium", or "low"
    """
    # High confidence: strong signal + good coverage
    if (
        signal_score >= CONFIDENCE_HIGH_SIGNAL
        and entity_count >= CONFIDENCE_HIGH_ENTITIES
        and (neighbor_count >= CONFIDENCE_HIGH_NEIGHBORS or path_count >= CONFIDENCE_HIGH_PATHS)
    ):
        return "high"

    # Medium confidence: decent signal or coverage
    if signal_score >= CONFIDENCE_MEDIUM_SIGNAL or (
        entity_count >= CONFIDENCE_MEDIUM_ENTITIES and neighbor_count >= CONFIDENCE_MEDIUM_NEIGHBORS
    ):
        return "medium"

    # Low confidence: weak signal and poor coverage
    return "low"
