import logging
import threading
import time

from neo4j import GraphDatabase
from neo4j.exceptions import ClientError, CypherSyntaxError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


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

    def _execute_query_safe(self, session, cypher: str, query_type: str | None = None, **params):
        """
        Execute a Cypher query with validation, error handling, and retry logic.

        Args:
            session: Neo4j session
            cypher: Cypher query string
            query_type: Type of query for fallback (e.g., "entity_neighbors", "entity_paths_2hop")
            **params: Query parameters

        Returns:
            Query result

        Raises:
            Exception: If query fails and cannot be retried
        """
        from app.graph.knowledge.cypher_validation import get_simpler_query, validate_cypher_query

        # Validate query before execution
        validation = validate_cypher_query(cypher)
        if not validation.is_valid:
            logger.warning("Cypher query validation failed: %s (type: %s)", validation.error, validation.error_type)
            # Try to get a simpler query if validation fails
            if query_type:
                allowed_sources = params.get("allowed_sources")
                simpler_query = get_simpler_query(query_type, allowed_sources)
                if simpler_query:
                    logger.info("Retrying with simpler query for type: %s", query_type)
                    try:
                        return session.run(simpler_query, **params)
                    except Exception as retry_error:
                        logger.exception("Simpler query also failed: %s", retry_error)
                        # Fall through to original execution attempt

        try:
            return session.run(cypher, **params)
        except (CypherSyntaxError, ClientError):
            logger.exception("Cypher query execution failed")
            logger.debug("Failed query: %s", cypher)

            # Try simpler query on execution failure
            if query_type:
                allowed_sources = params.get("allowed_sources")
                simpler_query = get_simpler_query(query_type, allowed_sources)
                if simpler_query:
                    logger.info("Retrying with simpler query after execution error for type: %s", query_type)
                    try:
                        return session.run(simpler_query, **params)
                    except Exception as retry_error:
                        logger.exception("Simpler query also failed: %s", retry_error)

            raise

    def upsert_triplet(
        self,
        head: str,
        relation: str,
        tail: str,
        source: str,
        chunk_id: str = "",
        page: int | None = None,
        confidence: float = 0.7,
    ):
        cypher = """
        MERGE (h:Entity {name: $head})
        MERGE (t:Entity {name: $tail})
        MERGE (s:Source {name: $source})
        MERGE (h)-[r:RELATED {type: $relation}]->(t)
        SET r.sources = CASE
            WHEN r.sources IS NULL THEN [$source]
            WHEN $source IN r.sources THEN r.sources
            ELSE r.sources + $source
        END,
        r.chunk_ids = CASE
            WHEN $chunk_id = "" THEN coalesce(r.chunk_ids, [])
            WHEN r.chunk_ids IS NULL THEN [$chunk_id]
            WHEN $chunk_id IN r.chunk_ids THEN r.chunk_ids
            ELSE r.chunk_ids + $chunk_id
        END,
        r.pages = CASE
            WHEN $page IS NULL THEN coalesce(r.pages, [])
            WHEN r.pages IS NULL THEN [$page]
            WHEN $page IN r.pages THEN r.pages
            ELSE r.pages + $page
        END,
        r.confidence_max = CASE
            WHEN r.confidence_max IS NULL OR $confidence > r.confidence_max THEN $confidence
            ELSE r.confidence_max
        END,
        r.confidence_count = coalesce(r.confidence_count, 0) + 1,
        r.confidence_avg = CASE
            WHEN r.confidence_avg IS NULL THEN $confidence
            ELSE ((r.confidence_avg * (r.confidence_count - 1)) + $confidence) / r.confidence_count
        END
        MERGE (h)-[:MENTIONED_IN]->(s)
        MERGE (t)-[:MENTIONED_IN]->(s)
        RETURN h.name, r.type, t.name
        """
        with self.driver.session() as session:
            session.run(
                cypher,
                head=head,
                relation=relation,
                tail=tail,
                source=source,
                chunk_id=chunk_id,
                page=page,
                confidence=float(confidence),
            )

    def batch_upsert_triplets(
        self,
        triplets: list[dict],
        batch_size: int = 100,
    ) -> int:
        """
        Batch upsert multiple triplets for better performance (~10x faster than individual upserts).

        Args:
            triplets: List of triplet dicts with keys: head, relation, tail, source,
                     chunk_id (optional), page (optional), confidence
            batch_size: Number of triplets to process per transaction (default: 100)

        Returns:
            Total number of triplets processed

        Example:
            triplets = [
                {
                    "head": "Python", "relation": "is_a", "tail": "Language",
                    "source": "doc.txt", "chunk_id": "chunk_1", "page": 1, "confidence": 0.9
                },
                ...
            ]
            count = client.batch_upsert_triplets(triplets)
        """
        # Input validation
        if not isinstance(triplets, list):
            raise TypeError(f"triplets must be a list, got {type(triplets).__name__}")

        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError(f"batch_size must be a positive integer, got {batch_size}")

        if not triplets:
            return 0

        # Validate required fields in triplets
        for i, triplet in enumerate(triplets):
            if not isinstance(triplet, dict):
                raise TypeError(f"triplets[{i}] must be a dict, got {type(triplet).__name__}")

            required_fields = ["head", "relation", "tail", "source"]
            for field in required_fields:
                if field not in triplet:
                    raise ValueError(f"triplets[{i}] missing required field: {field}")
                if not isinstance(triplet[field], str):
                    raise TypeError(f"triplets[{i}][{field}] must be a string, got {type(triplet[field]).__name__}")
                if not triplet[field].strip():
                    raise ValueError(f"triplets[{i}][{field}] cannot be empty")

        # Cypher query using UNWIND for batch processing
        cypher = """
        UNWIND $batch AS triplet
        MERGE (h:Entity {name: triplet.head})
        MERGE (t:Entity {name: triplet.tail})
        MERGE (s:Source {name: triplet.source})
        SET s.document_id = triplet.document_id,
            s.version = triplet.version,
            s.tenant_id = triplet.tenant_id,
            s.owner_user_id = triplet.owner_user_id,
            s.visibility = triplet.visibility,
            s.acl_tags = triplet.acl_tags
        MERGE (h)-[r:RELATED {type: triplet.relation}]->(t)
        SET r.sources = CASE
            WHEN r.sources IS NULL THEN [triplet.source]
            WHEN triplet.source IN r.sources THEN r.sources
            ELSE r.sources + triplet.source
        END,
        r.chunk_ids = CASE
            WHEN triplet.chunk_id = "" THEN coalesce(r.chunk_ids, [])
            WHEN r.chunk_ids IS NULL THEN [triplet.chunk_id]
            WHEN triplet.chunk_id IN r.chunk_ids THEN r.chunk_ids
            ELSE r.chunk_ids + triplet.chunk_id
        END,
        r.pages = CASE
            WHEN triplet.page IS NULL THEN coalesce(r.pages, [])
            WHEN r.pages IS NULL THEN [triplet.page]
            WHEN triplet.page IN r.pages THEN r.pages
            ELSE r.pages + triplet.page
        END,
        r.confidence_max = CASE
            WHEN r.confidence_max IS NULL OR triplet.confidence > r.confidence_max THEN triplet.confidence
            ELSE r.confidence_max
        END,
        r.confidence_count = coalesce(r.confidence_count, 0) + 1,
        r.confidence_avg = CASE
            WHEN r.confidence_avg IS NULL THEN triplet.confidence
            ELSE ((r.confidence_avg * (r.confidence_count - 1)) + triplet.confidence) / r.confidence_count
        END
        MERGE (h)-[:MENTIONED_IN]->(s)
        MERGE (t)-[:MENTIONED_IN]->(s)
        """

        total_processed = 0
        start_time = time.time()

        with self.driver.session() as session:
            # Process in batches to avoid memory issues with large datasets
            num_batches = (len(triplets) + batch_size - 1) // batch_size
            logger.info(f"Processing {len(triplets)} triplets in {num_batches} batches of {batch_size}")

            for batch_idx, i in enumerate(range(0, len(triplets), batch_size), 1):
                batch_start = time.time()
                batch = triplets[i : i + batch_size]

                # Ensure all triplets have required fields with defaults
                normalized_batch = [
                    {
                        "head": t["head"],
                        "relation": t["relation"],
                        "tail": t["tail"],
                        "source": t["source"],
                        "chunk_id": t.get("chunk_id", ""),
                        "page": t.get("page"),
                        "document_id": t.get("document_id", ""),
                        "version": t.get("version"),
                        "tenant_id": t.get("tenant_id", ""),
                        "owner_user_id": t.get("owner_user_id", ""),
                        "visibility": t.get("visibility", "private"),
                        "acl_tags": t.get("acl_tags", ""),
                        "confidence": float(t.get("confidence", 0.7)),
                    }
                    for t in batch
                ]
                session.run(cypher, batch=normalized_batch)
                total_processed += len(batch)

                batch_time = time.time() - batch_start
                logger.debug(f"Batch {batch_idx}/{num_batches}: {len(batch)} triplets in {batch_time:.2f}s")

        total_time = time.time() - start_time
        triplets_per_sec = total_processed / total_time if total_time > 0 else 0
        logger.info(
            f"Batch upsert completed: {total_processed} triplets in {total_time:.2f}s "
            f"({triplets_per_sec:.1f} triplets/sec)"
        )

        return total_processed

    def search_entities(
        self, keywords: list[str], limit: int = 10, allowed_sources: list[str] | None = None
    ) -> list[dict]:
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
            return [dict(r) for r in self._execute_query_safe(session, cypher, query_type="entity_search", **params)]

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
            return [dict(r) for r in self._execute_query_safe(session, cypher, query_type="entity_neighbors", **params)]

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
            return [
                dict(r) for r in self._execute_query_safe(session, cypher, query_type="entity_paths_2hop", **params)
            ]

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
            if hasattr(session, "execute_write"):
                return int(session.execute_write(_tx_work))
            if hasattr(session, "write_transaction"):
                return int(session.write_transaction(_tx_work))
            return int(_tx_work(session))

    def batch_entity_neighbors(
        self, entities: list[str], limit_per_entity: int = 10, allowed_sources: list[str] | None = None
    ) -> dict[str, list[dict]]:
        """
        Batch fetch neighbors for multiple entities in a single query (eliminates N+1 problem).

        Args:
            entities: List of entity names to fetch neighbors for
            limit_per_entity: Max neighbors per entity
            allowed_sources: Optional source filtering

        Returns:
            Dict mapping entity name to list of neighbor dicts

        Performance: 3 entities with 10 neighbors each = 1 query instead of 3 queries
        """
        if not entities:
            return {}

        if allowed_sources is not None:
            if not allowed_sources:
                return {e: [] for e in entities}
            cypher = """
            UNWIND $entities AS entity_name
            MATCH (e:Entity {name: entity_name})-[r:RELATED]-(o:Entity)
            WHERE any(src IN coalesce(r.sources, []) WHERE src IN $allowed_sources)
            WITH e.name AS entity, r.type AS relation, o.name AS other
            ORDER BY entity, relation, other
            RETURN entity, collect({relation: relation, other: other})[..$limit] AS neighbors
            """
            params = {"entities": entities, "limit": limit_per_entity, "allowed_sources": allowed_sources}
        else:
            cypher = """
            UNWIND $entities AS entity_name
            MATCH (e:Entity {name: entity_name})-[r:RELATED]-(o:Entity)
            WITH e.name AS entity, r.type AS relation, o.name AS other
            ORDER BY entity, relation, other
            RETURN entity, collect({relation: relation, other: other})[..$limit] AS neighbors
            """
            params = {"entities": entities, "limit": limit_per_entity}

        result = {}
        with self.driver.session() as session:
            for record in self._execute_query_safe(session, cypher, query_type="entity_neighbors", **params):
                entity_name = record["entity"]
                neighbors = record["neighbors"]
                # Flatten the neighbor structure
                result[entity_name] = [
                    {"entity": entity_name, "relation": n["relation"], "other": n["other"]} for n in neighbors
                ]

        # Ensure all requested entities are in result (even if no neighbors found)
        for entity in entities:
            if entity not in result:
                result[entity] = []

        return result

    def batch_entity_paths_2hop(
        self, entities: list[str], limit_per_entity: int = 8, allowed_sources: list[str] | None = None
    ) -> dict[str, list[dict]]:
        """
        Batch fetch 2-hop paths for multiple entities in a single query (eliminates N+1 problem).

        Args:
            entities: List of entity names to fetch paths for
            limit_per_entity: Max paths per entity
            allowed_sources: Optional source filtering

        Returns:
            Dict mapping entity name to list of path dicts

        Performance: 3 entities with 8 paths each = 1 query instead of 3 queries
        """
        if not entities:
            return {}

        if allowed_sources is not None:
            if not allowed_sources:
                return {e: [] for e in entities}
            cypher = """
            UNWIND $entities AS entity_name
            MATCH p=(e:Entity {name: entity_name})-[r1:RELATED]-(m:Entity)-[r2:RELATED]-(o:Entity)
            WHERE any(src IN coalesce(r1.sources, []) WHERE src IN $allowed_sources)
              AND any(src IN coalesce(r2.sources, []) WHERE src IN $allowed_sources)
              AND o.name <> e.name
            WITH e.name AS source, r1.type AS rel1, m.name AS middle, r2.type AS rel2, o.name AS target
            ORDER BY source, middle, target
            RETURN source, collect({rel1: rel1, middle: middle, rel2: rel2, target: target})[..$limit] AS paths
            """
            params = {"entities": entities, "limit": limit_per_entity, "allowed_sources": allowed_sources}
        else:
            cypher = """
            UNWIND $entities AS entity_name
            MATCH p=(e:Entity {name: entity_name})-[r1:RELATED]-(m:Entity)-[r2:RELATED]-(o:Entity)
            WHERE o.name <> e.name
            WITH e.name AS source, r1.type AS rel1, m.name AS middle, r2.type AS rel2, o.name AS target
            ORDER BY source, middle, target
            RETURN source, collect({rel1: rel1, middle: middle, rel2: rel2, target: target})[..$limit] AS paths
            """
            params = {"entities": entities, "limit": limit_per_entity}

        result = {}
        with self.driver.session() as session:
            for record in self._execute_query_safe(session, cypher, query_type="entity_paths_2hop", **params):
                source_name = record["source"]
                paths = record["paths"]
                # Flatten the path structure
                result[source_name] = [
                    {
                        "source": source_name,
                        "rel1": p["rel1"],
                        "middle": p["middle"],
                        "rel2": p["rel2"],
                        "target": p["target"],
                    }
                    for p in paths
                ]

        # Ensure all requested entities are in result (even if no paths found)
        for entity in entities:
            if entity not in result:
                result[entity] = []

        return result
