import logging

from app.tools.graph_tools import graph_lookup

logger = logging.getLogger(__name__)


def run_graph_rag(question: str, allowed_sources: list[str] | None = None) -> dict:
    try:
        graph_result = graph_lookup(question, allowed_sources=allowed_sources)
    except Exception as e:
        logger.exception(f"Graph lookup failed for question: {question}")
        return {
            "context": "",
            "entities": [],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.0,
            "error": f"graph_lookup_error:{type(e).__name__}",
        }

    entities = graph_result.get("entities", [])
    neighbors = graph_result.get("neighbors", [])
    paths = graph_result.get("paths", [])
    graph_signal_score = float(graph_result.get("graph_signal_score", 0.0) or 0.0)

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
                "Path2Hop: "
                f"{row['source']} -[{row.get('rel1', '')}]- {row['middle']} -[{row.get('rel2', '')}]- {row['target']}"
                f" | w={float(row.get('weight', 0)):.2f}"
            )

    return {
        "context": "\n".join(lines),
        "entities": [x.get("entity") for x in entities if x.get("entity")],
        "neighbors": neighbors,
        "paths": paths,
        "graph_signal_score": graph_signal_score,
    }
