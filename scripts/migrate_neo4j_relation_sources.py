from __future__ import annotations

import json

from neo4j import GraphDatabase

from app.core.config import get_settings


def main():
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    cypher = """
    MATCH (a:Entity)-[r:RELATED]-(b:Entity)
    OPTIONAL MATCH (a)-[:MENTIONED_IN]->(sa:Source)
    OPTIONAL MATCH (b)-[:MENTIONED_IN]->(sb:Source)
    WITH r, collect(DISTINCT sa.name) + collect(DISTINCT sb.name) AS all_sources
    WITH r, [x IN all_sources WHERE x IS NOT NULL] AS srcs
    SET r.sources = CASE
      WHEN r.sources IS NULL OR size(r.sources)=0 THEN srcs
      ELSE [x IN (r.sources + srcs) WHERE x IS NOT NULL]
    END
    RETURN count(r) AS touched
    """
    with driver.session() as session:
        row = session.run(cypher).single()
        touched = int(row["touched"]) if row else 0
    driver.close()
    print(json.dumps({"ok": True, "touched": touched}, ensure_ascii=False))


if __name__ == "__main__":
    main()
