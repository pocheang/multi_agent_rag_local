from neo4j import GraphDatabase

from app.core.config import get_settings


class Neo4jClient:
    def __init__(self):
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        self._init_schema()

    def close(self):
        self.driver.close()

    def _init_schema(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
            session.run("CREATE INDEX source_name IF NOT EXISTS FOR (s:Source) ON (s.name)")

    def upsert_triplet(self, head: str, relation: str, tail: str, source: str):
        cypher = """
        MERGE (h:Entity {name: $head})
        MERGE (t:Entity {name: $tail})
        MERGE (s:Source {name: $source})
        MERGE (h)-[r:RELATED {type: $relation}]->(t)
        MERGE (h)-[:MENTIONED_IN]->(s)
        MERGE (t)-[:MENTIONED_IN]->(s)
        RETURN h.name, r.type, t.name
        """
        with self.driver.session() as session:
            session.run(cypher, head=head, relation=relation, tail=tail, source=source)

    def search_entities(self, keywords: list[str], limit: int = 10, allowed_sources: list[str] | None = None) -> list[dict]:
        if allowed_sources is not None:
            if not allowed_sources:
                return []
            cypher = """
            MATCH (e:Entity)-[:MENTIONED_IN]->(s:Source)
            WHERE any(k IN $keywords WHERE toLower(e.name) CONTAINS toLower(k))
              AND s.name IN $allowed_sources
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            WHERE EXISTS {
              MATCH (e)-[:MENTIONED_IN]->(se:Source)
              MATCH (o)-[:MENTIONED_IN]->(so:Source)
              WHERE se.name IN $allowed_sources AND so.name IN $allowed_sources
            }
            RETURN e.name AS entity, collect(DISTINCT {relation: r.type, other: o.name})[..20] AS relations
            LIMIT $limit
            """
            params = {"keywords": keywords, "limit": limit, "allowed_sources": allowed_sources}
        else:
            cypher = """
            MATCH (e:Entity)
            WHERE any(k IN $keywords WHERE toLower(e.name) CONTAINS toLower(k))
            OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)
            RETURN e.name AS entity, collect(DISTINCT {relation: r.type, other: o.name})[..20] AS relations
            LIMIT $limit
            """
            params = {"keywords": keywords, "limit": limit}
        with self.driver.session() as session:
            return [dict(r) for r in session.run(cypher, **params)]

    def entity_neighbors(self, entity: str, limit: int = 10, allowed_sources: list[str] | None = None) -> list[dict]:
        if allowed_sources is not None:
            if not allowed_sources:
                return []
            cypher = """
            MATCH (e:Entity {name: $entity})-[r:RELATED]-(o:Entity)
            WHERE EXISTS {
              MATCH (e)-[:MENTIONED_IN]->(se:Source)
              MATCH (o)-[:MENTIONED_IN]->(so:Source)
              WHERE se.name IN $allowed_sources AND so.name IN $allowed_sources
            }
            RETURN e.name AS entity, r.type AS relation, o.name AS other
            LIMIT $limit
            """
            params = {"entity": entity, "limit": limit, "allowed_sources": allowed_sources}
        else:
            cypher = """
            MATCH (e:Entity {name: $entity})-[r:RELATED]-(o:Entity)
            RETURN e.name AS entity, r.type AS relation, o.name AS other
            LIMIT $limit
            """
            params = {"entity": entity, "limit": limit}
        with self.driver.session() as session:
            return [dict(r) for r in session.run(cypher, **params)]

    def entity_paths_2hop(self, entity: str, limit: int = 8, allowed_sources: list[str] | None = None) -> list[dict]:
        if allowed_sources is not None:
            if not allowed_sources:
                return []
            cypher = """
            MATCH p=(e:Entity {name: $entity})-[r1:RELATED]-(m:Entity)-[r2:RELATED]-(o:Entity)
            WHERE o.name <> e.name
              AND EXISTS {
                MATCH (e)-[:MENTIONED_IN]->(se:Source)
                MATCH (m)-[:MENTIONED_IN]->(sm:Source)
                MATCH (o)-[:MENTIONED_IN]->(so:Source)
                WHERE se.name IN $allowed_sources AND sm.name IN $allowed_sources AND so.name IN $allowed_sources
              }
            RETURN e.name AS source, r1.type AS rel1, m.name AS middle, r2.type AS rel2, o.name AS target
            LIMIT $limit
            """
            params = {"entity": entity, "limit": limit, "allowed_sources": allowed_sources}
        else:
            cypher = """
            MATCH p=(e:Entity {name: $entity})-[r1:RELATED]-(m:Entity)-[r2:RELATED]-(o:Entity)
            WHERE o.name <> e.name
            RETURN e.name AS source, r1.type AS rel1, m.name AS middle, r2.type AS rel2, o.name AS target
            LIMIT $limit
            """
            params = {"entity": entity, "limit": limit}
        with self.driver.session() as session:
            return [dict(r) for r in session.run(cypher, **params)]


    def delete_by_source(self, source: str) -> int:
        count_cypher = """
        MATCH (:Entity)-[r:RELATED]-(:Entity)
        WITH r
        WHERE EXISTS { MATCH (a:Entity)-[:MENTIONED_IN]->(:Source {name: $source}) WHERE a = startNode(r) }
          AND EXISTS { MATCH (b:Entity)-[:MENTIONED_IN]->(:Source {name: $source}) WHERE b = endNode(r) }
        RETURN count(r) AS rel_count
        """
        delete_relation_cypher = """
        MATCH (:Entity)-[r:RELATED]-(:Entity)
        WITH r
        WHERE EXISTS { MATCH (a:Entity)-[:MENTIONED_IN]->(:Source {name: $source}) WHERE a = startNode(r) }
          AND EXISTS { MATCH (b:Entity)-[:MENTIONED_IN]->(:Source {name: $source}) WHERE b = endNode(r) }
        DELETE r
        """
        delete_cypher = """
        MATCH (s:Source {name: $source})
        OPTIONAL MATCH (e:Entity)-[m:MENTIONED_IN]->(s)
        DELETE m
        WITH s
        DETACH DELETE s
        WITH 1 as _
        MATCH (e:Entity)
        WHERE NOT (e)--()
        DELETE e
        """
        with self.driver.session() as session:
            rel_count = session.run(count_cypher, source=source).single()
            count = int(rel_count["rel_count"]) if rel_count else 0
            session.run(delete_relation_cypher, source=source)
            session.run(delete_cypher, source=source)
            return count
