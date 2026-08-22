"""Database query optimization utilities."""

import logging
import re
from typing import Any

from sqlalchemy import Index, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# 安全修复：白名单允许的表名
ALLOWED_TABLES = {
    "users",
    "auth_sessions",
    "audit_logs",
    "oauth_identities",
    "system_settings",
    "session_metadata",
}


def _dialect_name(session: Any) -> str:
    """Return the SQLAlchemy dialect name for a session or connection."""
    dialect = getattr(session, "dialect", None)
    if dialect is None:
        bind = getattr(session, "bind", None)
        if bind is None:
            get_bind = getattr(session, "get_bind", None)
            if callable(get_bind):
                bind = get_bind()
        dialect = getattr(bind, "dialect", None)
    return str(getattr(dialect, "name", "") or "").lower()


def _validated_identifier(value: str) -> str:
    """
    验证SQL标识符（表名、列名）的安全性

    安全修复：
    1. 严格的正则表达式验证
    2. 白名单检查
    3. 长度限制

    Args:
        value: 要验证的标识符

    Returns:
        验证通过的标识符

    Raises:
        ValueError: 标识符不合法
    """
    identifier = str(value or "").strip()

    # 长度检查
    if not identifier or len(identifier) > 64:
        raise ValueError(f"Invalid SQL identifier length: {value!r}")

    # 正则表达式验证
    if not _SQL_IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"Invalid SQL identifier format: {value!r}")

    # 白名单检查
    if identifier not in ALLOWED_TABLES:
        raise ValueError(f"Table not in whitelist: {value!r}")

    return identifier


class QueryOptimizer:
    """Database query optimization utilities."""

    @staticmethod
    async def analyze_table(session: AsyncSession, table_name: str) -> None:
        """Run ANALYZE on a table to update statistics.

        Args:
            session: Database session
            table_name: Name of table to analyze

        Raises:
            ValueError: If table_name is not in whitelist
        """
        table_name = _validated_identifier(table_name)
        # 使用参数化查询（虽然ANALYZE不支持参数，但已通过白名单验证）
        await session.execute(text(f'ANALYZE "{table_name}"'))
        logger.info(f"Analyzed table: {table_name}")

    @staticmethod
    async def vacuum_table(
        session: AsyncSession,
        table_name: str,
        full: bool = False,
    ) -> None:
        """Run VACUUM on a table to reclaim space.

        Args:
            session: Database session
            table_name: Name of table to vacuum
            full: Whether to run VACUUM FULL

        Raises:
            ValueError: If table_name is not in whitelist
        """
        table_name = _validated_identifier(table_name)
        vacuum_cmd = "VACUUM FULL" if full else "VACUUM"
        await session.execute(text(f'{vacuum_cmd} "{table_name}"'))
        logger.info(f"Vacuumed table: {table_name}")

    @staticmethod
    async def get_table_stats(
        session: AsyncSession,
        table_name: str,
    ) -> dict[str, Any]:
        """Get statistics for a table.

        Args:
            session: Database session
            table_name: Name of table

        Returns:
            Dictionary with table statistics

        Raises:
            ValueError: If table_name is not in whitelist
        """
        table_name = _validated_identifier(table_name)
        try:
            # Get row count
            result = await session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = result.scalar()

            size_bytes = None
            size_pretty = None
            if _dialect_name(session) == "postgresql":
                result = await session.execute(
                    text(
                        f"SELECT pg_total_relation_size('{table_name}') as size, "
                        f"pg_size_pretty(pg_total_relation_size('{table_name}')) as size_pretty"
                    )
                )
                size_info = result.fetchone()
                if size_info:
                    size_bytes = size_info[0]
                    size_pretty = size_info[1]

            return {
                "table": table_name,
                "row_count": row_count,
                "size_bytes": size_bytes,
                "size_pretty": size_pretty,
            }
        except Exception as e:
            logger.error(f"Error getting stats for {table_name}: {e}")
            raise

    @staticmethod
    async def get_slow_queries(
        session: AsyncSession,
        min_duration_ms: int = 1000,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get slow queries from pg_stat_statements.

        Args:
            session: Database session
            min_duration_ms: Minimum query duration in milliseconds
            limit: Maximum number of queries to return

        Returns:
            List of slow queries with statistics
        """
        if _dialect_name(session) != "postgresql":
            logger.info("Slow-query statistics are unavailable for non-PostgreSQL databases")
            return []

        try:
            query = text(
                """
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    max_exec_time,
                    rows
                FROM pg_stat_statements
                WHERE mean_exec_time > :min_duration
                ORDER BY mean_exec_time DESC
                LIMIT :limit
                """
            )

            result = await session.execute(
                query,
                {"min_duration": min_duration_ms, "limit": limit},
            )

            return [
                {
                    "query": row[0],
                    "calls": row[1],
                    "total_time_ms": row[2],
                    "mean_time_ms": row[3],
                    "max_time_ms": row[4],
                    "rows": row[5],
                }
                for row in result.fetchall()
            ]
        except Exception as e:
            logger.error(f"Error getting slow queries: {e}")
            raise

    @staticmethod
    async def explain_query(
        session: AsyncSession,
        query: str,
        analyze: bool = False,
    ) -> str:
        """Get EXPLAIN output for a query.

        安全修复：禁用此功能以防止SQL注入
        此方法接受原始SQL查询，存在严重的SQL注入风险。
        建议使用专门的查询分析工具或ORM的explain功能。

        Args:
            session: Database session
            query: SQL query to explain
            analyze: Whether to run EXPLAIN ANALYZE

        Returns:
            EXPLAIN output as string

        Raises:
            NotImplementedError: 此功能已禁用
        """
        # 安全修复：完全禁用此功能
        raise NotImplementedError(
            "explain_query is disabled for security reasons. "
            "Use database-specific tools or ORM explain functionality instead."
        )

    @staticmethod
    def create_index_recommendations(
        table_name: str,
        columns: list[str],
    ) -> list[Index]:
        """Generate index recommendations.

        Args:
            table_name: Name of table
            columns: Columns to index

        Returns:
            List of recommended indexes

        Raises:
            ValueError: If table_name is not in whitelist
        """
        # 验证表名
        table_name = _validated_identifier(table_name)

        # 验证列名
        for col in columns:
            if not _SQL_IDENTIFIER.fullmatch(col):
                raise ValueError(f"Invalid column name: {col!r}")

        indexes = []

        # Single column indexes
        for col in columns:
            idx_name = f"idx_{table_name}_{col}"
            indexes.append(Index(idx_name, col))

        # Common composite indexes (for common query patterns)
        if "user_id" in columns and "created_at" in columns:
            indexes.append(
                Index(
                    f"idx_{table_name}_user_created",
                    "user_id",
                    "created_at",
                )
            )

        if "session_id" in columns and "timestamp" in columns:
            indexes.append(
                Index(
                    f"idx_{table_name}_session_time",
                    "session_id",
                    "timestamp",
                )
            )

        return indexes


async def optimize_database(session: AsyncSession, tables: list[str]) -> dict[str, Any]:
    """Run optimization tasks on database.

    Args:
        session: Database session
        tables: List of table names to optimize

    Returns:
        Dictionary with optimization results

    Raises:
        ValueError: If any table_name is not in whitelist
    """
    optimizer = QueryOptimizer()
    results = {}

    for table in tables:
        # 验证会在这里抛出异常
        table = _validated_identifier(table)
        await optimizer.analyze_table(session, table)
        results[table] = await optimizer.get_table_stats(session, table)

    return results
