from neo4j import GraphDatabase
import threading

from app.core.config import get_settings


class Neo4jClient:
    _driver = None
    _schema_inited = False
    _schema_init_in_progress = False
    _lock = threading.Lock()
    _schema_cv = threading.Condition(_lock)

    def __init__(self):
        self.driver = self._shared_driver()
        self._ensure_schema()

    def close(self):
        # Shared driver lifecycle is managed at process level.
        return None

    @classmethod
    def close_shared_driver(cls) -> None:
        with cls._schema_cv:
            driver = cls._driver
            cls._driver = None
            cls._schema_inited = False
            cls._schema_init_in_progress = False
            cls._schema_cv.notify_all()
        if driver is not None:
            driver.close()

    @classmethod
    def _shared_driver(cls):
        with cls._lock:
            if cls._driver is None:
                settings = get_settings()
                cls._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password),
                    max_connection_lifetime=1800,
                )
            return cls._driver

    def _ensure_schema(self):
        with self.__class__._schema_cv:
            while True:
                if self.__class__._schema_inited:
                    return
                if not self.__class__._schema_init_in_progress:
                    self.__class__._schema_init_in_progress = True
                    break
                self.__class__._schema_cv.wait()
        ok = False
        try:
            with self.driver.session() as session:
                session.run("CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
                session.run("CREATE INDEX source_name IF NOT EXISTS FOR (s:Source) ON (s.name)")
            ok = True
        finally:
            with self.__class__._schema_cv:
                self.__class__._schema_inited = bool(ok)
                self.__class__._schema_init_in_progress = False
                self.__class__._schema_cv.notify_all()

    def upsert_triplet(self, head: str, relation: str, tail: str, source: str):
        cypher = """
        MERGE (h:Entity {name: $head})
        MERGE (t:Entity {name: $tail})
        MERGE (s:Source {name: $source})
        MERGE (h)-[r:RELATED {type: $relation}]->(t)
        SET r.sources = CASE
            WHEN r.sources IS NULL THEN [$source]
            WHEN $source IN r.sources THEN r.sources
            ELSE r.sources + $source
        END
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
            WHERE any(src IN coalesce(r.sources, []) WHERE src IN $allowed_sources)
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
            WHERE any(src IN coalesce(r.sources, []) WHERE src IN $allowed_sources)
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
              AND any(src IN coalesce(r1.sources, []) WHERE src IN $allowed_sources)
              AND any(src IN coalesce(r2.sources, []) WHERE src IN $allowed_sources)
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
        MATCH ()-[r:RELATED]-()
        WHERE $source IN coalesce(r.sources, [])
        RETURN count(r) AS rel_count
        """
        trim_relation_cypher = """
        MATCH ()-[r:RELATED]-()
        WHERE $source IN coalesce(r.sources, [])
        WITH r, [x IN coalesce(r.sources, []) WHERE x <> $source] AS remain_sources
        FOREACH (_ IN CASE WHEN size(remain_sources) = 0 THEN [1] ELSE [] END | DELETE r)
        FOREACH (_ IN CASE WHEN size(remain_sources) > 0 THEN [1] ELSE [] END | SET r.sources = remain_sources)
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

        def _tx_work(tx):
            rel_count = tx.run(count_cypher, source=source).single()
            count = int(rel_count["rel_count"]) if rel_count else 0
            tx.run(trim_relation_cypher, source=source)
            tx.run(delete_cypher, source=source)
            return count

        with self.driver.session() as session:
            return int(session.execute_write(_tx_work))
