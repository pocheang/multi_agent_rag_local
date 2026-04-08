from app.tools.graph_tools import graph_lookup


def run_graph_rag(question: str, allowed_sources: list[str] | None = None) -> dict:
    graph_result = graph_lookup(question, allowed_sources=allowed_sources)
    entities = graph_result.get("entities", [])
    neighbors = graph_result.get("neighbors", [])

    lines = []
    for item in entities:
        name = item.get("entity", "")
        if not name:
            continue
        lines.append(f"Entity: {name}")
        for rel in item.get("relations", []):
            if rel.get("other"):
                lines.append(f"  - {rel.get('relation')} -> {rel.get('other')}")

    for row in neighbors:
        if row.get("entity") and row.get("relation") and row.get("other"):
            lines.append(f"Neighbor: {row['entity']} -[{row['relation']}]- {row['other']}")

    return {
        "context": "\n".join(lines),
        "entities": [x.get("entity") for x in entities if x.get("entity")],
        "neighbors": neighbors,
    }
