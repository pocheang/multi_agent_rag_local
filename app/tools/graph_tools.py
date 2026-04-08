import re

from app.graph.neo4j_client import Neo4jClient

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}")


def graph_lookup(question: str, allowed_sources: list[str] | None = None) -> dict:
    tokens = TOKEN_PATTERN.findall(question)
    client = Neo4jClient()
    try:
        entities = client.search_entities(tokens, limit=8, allowed_sources=allowed_sources)
        entity_names = [x["entity"] for x in entities]
        neighbor_rows = []
        for name in entity_names[:3]:
            neighbor_rows.extend(client.entity_neighbors(name, limit=8, allowed_sources=allowed_sources))
        return {"entities": entities, "neighbors": neighbor_rows}
    finally:
        client.close()
