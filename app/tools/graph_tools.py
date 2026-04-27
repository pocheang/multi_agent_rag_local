import re

from app.graph.neo4j_client import Neo4jClient
from app.services.bulkhead import bulkhead
from app.services.resilience import call_with_circuit_breaker

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}")
_NOISY_RELATIONS = {"related", "关联", "相关", "link", "links", "unknown", "其他"}
_ENTITY_ALIASES = {
    "ai": "artificial intelligence",
    "a.i.": "artificial intelligence",
    "llm": "large language model",
    "大模型": "large language model",
    "网络安全": "cybersecurity",
    "资安": "cybersecurity",
}


def _normalize_token(token: str) -> str:
    t = str(token or "").strip().lower()
    if not t:
        return ""
    return _ENTITY_ALIASES.get(t, t)


def _normalize_entity_name(name: str) -> str:
    return _normalize_token(name)


def _relation_weight(rel: str) -> float:
    r = str(rel or "").strip().lower()
    if not r:
        return 0.0
    if r in _NOISY_RELATIONS:
        return 0.0
    if any(k in r for k in ("causes", "导致", "depends", "依赖", "uses", "利用", "targets", "攻击", "mitigates", "缓解")):
        return 1.0
    return 0.6


def graph_lookup(question: str, allowed_sources: list[str] | None = None) -> dict:
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
            for name in lookup_entity_names[:3]:
                # Fix lambda capture bug: capture name in local scope
                current_name = name
                rows = call_with_circuit_breaker(
                    "neo4j.entity_neighbors",
                    lambda n=current_name: client.entity_neighbors(n, limit=10, allowed_sources=allowed_sources),
                )
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
                paths = call_with_circuit_breaker(
                    "neo4j.entity_paths_2hop",
                    lambda n=current_name: client.entity_paths_2hop(n, limit=8, allowed_sources=allowed_sources),
                )
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

            # Calculate graph signal score with balanced weighting
            # Each component is normalized to [0, 1] before weighted averaging
            entity_score = min(1.0, len(normalized_entities) / 4.0)

            # Neighbor score: average weight of top neighbors
            neighbor_weights = [float(x.get("weight", 0.0)) for x in neighbor_rows[:12]]
            if neighbor_weights:
                neighbor_score = sum(neighbor_weights) / len(neighbor_weights)
                neighbor_score = min(1.0, neighbor_score)
            else:
                neighbor_score = 0.0

            # Path score: average weight of top paths
            path_weights = [float(x.get("weight", 0.0)) for x in path_rows[:8]]
            if path_weights:
                path_score = sum(path_weights) / len(path_weights)
                path_score = min(1.0, path_score)
            else:
                path_score = 0.0

            # Weighted average: entities (30%), neighbors (40%), paths (30%)
            # Only include components that have data
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
