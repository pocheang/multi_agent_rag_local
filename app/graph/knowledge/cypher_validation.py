"""
Cypher query validation and error handling.

This module provides validation logic to ensure Cypher queries are safe and well-formed
before execution, and provides query templates for common patterns.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of Cypher query validation."""

    is_valid: bool
    error: str | None = None
    error_type: str | None = None


@dataclass
class CypherQueryTemplate:
    """Template for common Cypher query patterns."""

    name: str
    query: str
    params: list[str]
    description: str = ""


# Unsafe operations that should not be allowed in read-only queries
UNSAFE_OPERATIONS = ["CREATE", "DELETE", "MERGE", "SET", "REMOVE", "DETACH"]

# Required clauses for valid Cypher queries
REQUIRED_MATCH = re.compile(r"\bMATCH\b", re.IGNORECASE)
REQUIRED_RETURN = re.compile(r"\bRETURN\b", re.IGNORECASE)


def validate_cypher_query(query: str) -> ValidationResult:
    """
    Validate a Cypher query for safety and correctness.

    Args:
        query: Cypher query string to validate

    Returns:
        ValidationResult with validation status and error details
    """
    if not query or not query.strip():
        return ValidationResult(
            is_valid=False,
            error="Query is empty",
            error_type="empty_query"
        )

    query_upper = query.upper()

    # Check for unsafe operations
    for operation in UNSAFE_OPERATIONS:
        if re.search(rf"\b{operation}\b", query_upper):
            return ValidationResult(
                is_valid=False,
                error=f"Unsafe operation detected: {operation}",
                error_type="unsafe_operation"
            )

    # Check for required clauses
    if not REQUIRED_MATCH.search(query):
        return ValidationResult(
            is_valid=False,
            error="Query must contain MATCH clause",
            error_type="missing_match"
        )

    if not REQUIRED_RETURN.search(query):
        return ValidationResult(
            is_valid=False,
            error="Query must contain RETURN clause",
            error_type="missing_return"
        )

    # Basic syntax validation - check for balanced braces and parentheses
    try:
        _check_balanced_brackets(query)
    except ValueError as e:
        return ValidationResult(
            is_valid=False,
            error=str(e),
            error_type="syntax_error"
        )

    return ValidationResult(is_valid=True)


def _check_balanced_brackets(query: str) -> None:
    """
    Check if brackets are balanced in the query.

    Args:
        query: Cypher query string

    Raises:
        ValueError: If brackets are not balanced
    """
    stack = []
    pairs = {"(": ")", "{": "}", "[": "]"}

    for char in query:
        if char in pairs:
            stack.append(char)
        elif char in pairs.values():
            if not stack:
                raise ValueError(f"Unmatched closing bracket: {char}")
            opening = stack.pop()
            if pairs[opening] != char:
                raise ValueError(f"Mismatched brackets: {opening} and {char}")

    if stack:
        raise ValueError(f"Unmatched opening bracket: {stack[-1]}")


def get_query_templates() -> list[CypherQueryTemplate]:
    """
    Get common Cypher query templates.

    Returns:
        List of CypherQueryTemplate objects for common patterns
    """
    return [
        CypherQueryTemplate(
            name="entity_search",
            query="""
            MATCH (e:Entity)
            WHERE any(k IN $keywords WHERE toLower(e.name) CONTAINS toLower(k))
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            RETURN e.name AS entity, collect(DISTINCT {relation: r.type, other: o.name})[..20] AS relations
            LIMIT $limit
            """,
            params=["keywords", "limit"],
            description="Search for entities by keywords"
        ),
        CypherQueryTemplate(
            name="entity_neighbors",
            query="""
            MATCH (e:Entity {name: $entity})-[r:RELATED]-(o:Entity)
            RETURN e.name AS entity, r.type AS relation, o.name AS other
            LIMIT $limit
            """,
            params=["entity", "limit"],
            description="Get neighbors of a specific entity"
        ),
        CypherQueryTemplate(
            name="entity_paths_2hop",
            query="""
            MATCH p=(e:Entity {name: $entity})-[r1:RELATED]-(m:Entity)-[r2:RELATED]-(o:Entity)
            WHERE o.name <> e.name
            RETURN e.name AS source, r1.type AS rel1, m.name AS middle, r2.type AS rel2, o.name AS target
            LIMIT $limit
            """,
            params=["entity", "limit"],
            description="Get 2-hop paths from a specific entity"
        ),
        CypherQueryTemplate(
            name="entity_search_with_sources",
            query="""
            MATCH (e:Entity)-[:MENTIONED_IN]->(s:Source)
            WHERE any(k IN $keywords WHERE toLower(e.name) CONTAINS toLower(k))
              AND s.name IN $allowed_sources
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            WHERE any(src IN coalesce(r.sources, []) WHERE src IN $allowed_sources)
            RETURN e.name AS entity, collect(DISTINCT {relation: r.type, other: o.name})[..20] AS relations
            LIMIT $limit
            """,
            params=["keywords", "allowed_sources", "limit"],
            description="Search for entities with source filtering"
        ),
        CypherQueryTemplate(
            name="entity_neighbors_with_sources",
            query="""
            MATCH (e:Entity {name: $entity})-[r:RELATED]-(o:Entity)
            WHERE any(src IN coalesce(r.sources, []) WHERE src IN $allowed_sources)
            RETURN e.name AS entity, r.type AS relation, o.name AS other
            LIMIT $limit
            """,
            params=["entity", "allowed_sources", "limit"],
            description="Get neighbors with source filtering"
        ),
        CypherQueryTemplate(
            name="entity_paths_2hop_with_sources",
            query="""
            MATCH p=(e:Entity {name: $entity})-[r1:RELATED]-(m:Entity)-[r2:RELATED]-(o:Entity)
            WHERE o.name <> e.name
              AND any(src IN coalesce(r1.sources, []) WHERE src IN $allowed_sources)
              AND any(src IN coalesce(r2.sources, []) WHERE src IN $allowed_sources)
            RETURN e.name AS source, r1.type AS rel1, m.name AS middle, r2.type AS rel2, o.name AS target
            LIMIT $limit
            """,
            params=["entity", "allowed_sources", "limit"],
            description="Get 2-hop paths with source filtering"
        ),
    ]


def get_simpler_query(query_type: str, allowed_sources: list[str] | None = None) -> str | None:
    """
    Get a simpler fallback query for a given query type.

    Args:
        query_type: Type of query (e.g., "entity_neighbors", "entity_paths_2hop")
        allowed_sources: Optional list of allowed document sources

    Returns:
        Simpler Cypher query string or None if no fallback available
    """
    templates = get_query_templates()

    # Fallback strategy: remove complex clauses
    if query_type == "entity_paths_2hop":
        # Fall back to neighbors if 2-hop paths fail
        template_name = "entity_neighbors_with_sources" if allowed_sources else "entity_neighbors"
        template = next((t for t in templates if t.name == template_name), None)
        return template.query if template else None

    if query_type == "entity_neighbors":
        # Fall back to basic entity search if neighbors fail
        template_name = "entity_search_with_sources" if allowed_sources else "entity_search"
        template = next((t for t in templates if t.name == template_name), None)
        return template.query if template else None

    return None

