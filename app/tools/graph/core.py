import re

from app.domain.text import normalize_string
from app.graph.knowledge.client import Neo4jClient
from app.services.runtime.bulkhead import bulkhead
from app.services.runtime.resilience import call_with_circuit_breaker

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}")
_NOISY_RELATIONS = {
    "related",
    "\u5173\u8054",
    "\u76f8\u5173",
    "link",
    "links",
    "unknown",
    "\u5176\u4ed6",
}
_ENTITY_ALIASES = {
    "ai": "artificial intelligence",
    "a.i.": "artificial intelligence",
    "llm": "large language model",
    "\u5927\u6a21\u578b": "large language model",
    "\u7f51\u7edc\u5b89\u5168": "cybersecurity",
    "\u8d44\u5b89": "cybersecurity",
}
_RELATION_KEYWORDS = (
    "causes",
    "\u5bfc\u81f4",
    "depends",
    "\u4f9d\u8d56",
    "uses",
    "\u5229\u7528",
    "targets",
    "\u653b\u51fb",
    "mitigates",
    "\u7f13\u89e3",
)


def _normalize_token(token: str) -> str:
    t = normalize_string(token, lowercase=True)
    if not t:
        return ""
    return _ENTITY_ALIASES.get(t, t)


def _normalize_entity_name(name: str) -> str:
    return _normalize_token(name)


def _relation_weight(rel: str) -> float:
    r = normalize_string(rel, lowercase=True)
    if not r:
        return 0.0
    if r in _NOISY_RELATIONS:
        return 0.0
    if any(keyword in r for keyword in _RELATION_KEYWORDS):
        return 1.0
    return 0.6


def _fetch_neighbors(
    client: Neo4jClient, entities_to_lookup: list[str], allowed_sources: list[str] | None
) -> dict[str, list[dict]]:
    if hasattr(client, "batch_entity_neighbors"):
        return call_with_circuit_breaker(
            "neo4j.batch_entity_neighbors",
            lambda: client.batch_entity_neighbors(
                entities_to_lookup,
                limit_per_entity=10,
                allowed_sources=allowed_sources,
            ),
        )

    return {
        entity_name: call_with_circuit_breaker(
            "neo4j.entity_neighbors",
            lambda entity_name=entity_name: client.entity_neighbors(
                entity_name,
                limit=10,
                allowed_sources=allowed_sources,
            ),
        )
        for entity_name in entities_to_lookup
    }


def _fetch_paths(
    client: Neo4jClient, entities_to_lookup: list[str], allowed_sources: list[str] | None
) -> dict[str, list[dict]]:
    if hasattr(client, "batch_entity_paths_2hop"):
        return call_with_circuit_breaker(
            "neo4j.batch_entity_paths_2hop",
            lambda: client.batch_entity_paths_2hop(
                entities_to_lookup,
                limit_per_entity=8,
                allowed_sources=allowed_sources,
            ),
        )

    return {
        entity_name: call_with_circuit_breaker(
            "neo4j.entity_paths_2hop",
            lambda entity_name=entity_name: client.entity_paths_2hop(
                entity_name,
                limit=8,
                allowed_sources=allowed_sources,
            ),
        )
        for entity_name in entities_to_lookup
    }


def graph_lookup(
    question: str, allowed_sources: list[str] | None = None, use_robust_extraction: bool | None = None
) -> dict:
    """
    Look up entities and relationships in the graph.

    Args:
        question: Query string
        allowed_sources: Optional list of allowed document sources
        use_robust_extraction: Use robust multi-stage entity extraction (default: from config)

    Returns:
        Dictionary with entities, neighbors, paths, and graph_signal_score
    """
    # Determine whether to use robust extraction (from config if not specified)
    if use_robust_extraction is None:
        from app.core.config import get_settings

        settings = get_settings()
        use_robust_extraction = settings.graph_entity_extraction_robust

    # Extract entities using robust extraction or fallback to simple tokenization
    if use_robust_extraction:
        try:
            from app.graph.knowledge.entity_extraction import extract_entities

            # Extract entities (LLM usage controlled by config)
            use_llm = settings.graph_entity_extraction_use_llm
            extracted = extract_entities(question, use_llm=use_llm)
            # Use extracted entity texts as tokens
            tokens = [e["text"] for e in extracted]
            # Normalize tokens
            tokens = [_normalize_token(t) for t in tokens if _normalize_token(t)]
        except Exception as e:
            # Fallback to simple tokenization on error
            import logging

            logging.getLogger(__name__).warning("Robust entity extraction failed, using fallback: %s", e)
            raw_tokens = TOKEN_PATTERN.findall(question)
            tokens = [_normalize_token(t) for t in raw_tokens if _normalize_token(t)]
    else:
        # Legacy simple tokenization
        raw_tokens = TOKEN_PATTERN.findall(question)
        tokens = [_normalize_token(t) for t in raw_tokens if _normalize_token(t)]

    with bulkhead("neo4j"):
        client = Neo4jClient()
        try:
            entities = call_with_circuit_breaker(
                "neo4j.search_entities",
                lambda: client.search_entities(tokens, limit=8, allowed_sources=allowed_sources),
            )
            normalized_entities = []
            lookup_entity_names = []
            for row in entities:
                raw_entity_name = str(row.get("entity", "")).strip()
                entity_name = _normalize_entity_name(raw_entity_name)
                if not entity_name:
                    continue
                normalized_rels = []
                for rel in row.get("relations", []) or []:
                    relation = str(rel.get("relation", "")).strip()
                    other = _normalize_entity_name(str(rel.get("other", "")).strip())
                    weight = _relation_weight(relation)
                    if not other or weight <= 0:
                        continue
                    normalized_rels.append({"relation": relation, "other": other, "weight": weight})
                normalized_entities.append({"entity": entity_name, "relations": normalized_rels})
                lookup_entity_names.append(raw_entity_name)

            neighbor_rows = []
            seen_neighbor: set[tuple[str, str, str]] = set()
            path_rows = []
            seen_path: set[tuple[str, str, str, str, str]] = set()
            entities_to_lookup = lookup_entity_names[:3]

            if entities_to_lookup:
                neighbors_by_entity = _fetch_neighbors(client, entities_to_lookup, allowed_sources)
                for rows in neighbors_by_entity.values():
                    for row in rows:
                        entity = _normalize_entity_name(str(row.get("entity", "")).strip())
                        relation = str(row.get("relation", "")).strip()
                        other = _normalize_entity_name(str(row.get("other", "")).strip())
                        weight = _relation_weight(relation)
                        if not entity or not other or weight <= 0:
                            continue
                        key = (entity, relation.lower(), other)
                        if key in seen_neighbor:
                            continue
                        seen_neighbor.add(key)
                        neighbor_rows.append({"entity": entity, "relation": relation, "other": other, "weight": weight})

                paths_by_entity = _fetch_paths(client, entities_to_lookup, allowed_sources)
                for paths in paths_by_entity.values():
                    for p in paths:
                        source = _normalize_entity_name(str(p.get("source", "")).strip())
                        middle = _normalize_entity_name(str(p.get("middle", "")).strip())
                        target = _normalize_entity_name(str(p.get("target", "")).strip())
                        rel1 = str(p.get("rel1", "")).strip()
                        rel2 = str(p.get("rel2", "")).strip()
                        w1 = _relation_weight(rel1)
                        w2 = _relation_weight(rel2)
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

            entity_score = min(1.0, len(normalized_entities) / 4.0)
            neighbor_weights = [float(x.get("weight", 0.0)) for x in neighbor_rows[:12]]
            neighbor_score = min(1.0, (sum(neighbor_weights) / len(neighbor_weights))) if neighbor_weights else 0.0
            path_weights = [float(x.get("weight", 0.0)) for x in path_rows[:8]]
            path_score = min(1.0, (sum(path_weights) / len(path_weights))) if path_weights else 0.0

            total_weight = 0.0
            weighted_sum = 0.0
            if normalized_entities:
                weighted_sum += 0.3 * entity_score
                total_weight += 0.3
            if neighbor_rows:
                weighted_sum += 0.4 * neighbor_score
                total_weight += 0.4
            if path_rows:
                weighted_sum += 0.3 * path_score
                total_weight += 0.3

            graph_signal_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
            return {
                "entities": normalized_entities,
                "neighbors": neighbor_rows,
                "paths": path_rows,
                "graph_signal_score": graph_signal_score,
            }
        finally:
            client.close()
