"""Database connection pool with optimization."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Optimized database connection pool manager."""

    def __init__(
        self,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo: bool = False,
    ):
        self.settings = get_settings()
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping
        self.echo = echo

        self._engine: AsyncEngine | None = None
        self._session_factory: sessionmaker | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self._lock:
            if self._engine is not None:
                logger.warning("Connection pool already initialized")
                return

            database_url = str(self.settings.database_url)
            if database_url.startswith("sqlite:///"):
                database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
            elif database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

            engine_kwargs: dict[str, Any] = {
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "pool_timeout": self.pool_timeout,
                "pool_recycle": self.pool_recycle,
                "pool_pre_ping": self.pool_pre_ping,
                "echo": self.echo,
            }
            if database_url.startswith(("postgresql+asyncpg://", "postgresql+psycopg://")):
                engine_kwargs["connect_args"] = {
                    "server_settings": {
                        "jit": "on",
                        "application_name": "querymind_rag",
                    }
                }

            self._engine = create_async_engine(database_url, **engine_kwargs)

            # Create session factory
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            logger.info(
                f"Database connection pool initialized: size={self.pool_size}, max_overflow={self.max_overflow}"
            )

    async def close(self) -> None:
        """Close the connection pool."""
        async with self._lock:
            if self._engine is None:
                return

            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session from the pool.

        Yields:
            AsyncSession instance
        """
        if self._session_factory is None:
            await self.initialize()

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def execute_batch(
        self,
        statements: list[str],
        params_list: list[dict[str, Any]] | None = None,
    ) -> list[Any]:
        """Execute multiple statements in a batch.

        Args:
            statements: SQL statements to execute
            params_list: Optional parameters for each statement

        Returns:
            List of results
        """
        if params_list is None:
            params_list = [{}] * len(statements)
        elif len(params_list) != len(statements):
            raise ValueError(
                f"params_list length must match statements length ({len(params_list)} != {len(statements)})"
            )

        results = []

        async with self.session() as session:
            for stmt, params in zip(statements, params_list, strict=False):
                result = await session.execute(text(stmt), params)
                results.append(result)

        return results

    def get_pool_stats(self) -> dict[str, Any]:
        """
        Get connection pool statistics.

        安全改进：添加更多监控指标

        Returns:
            Dictionary with pool stats
        """
        if self._engine is None:
            return {"status": "not_initialized"}

        pool = self._engine.pool

        # 基本统计
        stats = {
            "status": "active",
            "size": self.pool_size,
            "max_overflow": self.max_overflow,
        }

        # 连接状态统计
        if hasattr(pool, "checkedout"):
            checked_out = pool.checkedout()
            stats["checked_out"] = checked_out

            # 计算空闲连接数
            if hasattr(pool, "size"):
                pool_size = pool.size()
                stats["checked_in"] = pool_size - checked_out
                stats["total_connections"] = pool_size

        if hasattr(pool, "overflow"):
            stats["overflow"] = pool.overflow()

        # 超时统计（如果可用）
        if hasattr(pool, "_timeout_count"):
            stats["timeout_count"] = pool._timeout_count

        # 连接池利用率
        if "checked_out" in stats and "size" in stats:
            stats["utilization"] = stats["checked_out"] / stats["size"] if stats["size"] > 0 else 0

        return stats


# Global connection pool instance
_connection_pool: DatabaseConnectionPool | None = None


def get_connection_pool() -> DatabaseConnectionPool:
    """Get or create the global connection pool.

    Returns:
        DatabaseConnectionPool instance
    """
    global _connection_pool

    if _connection_pool is None:
        _connection_pool = DatabaseConnectionPool()

    return _connection_pool


async def initialize_pool() -> None:
    """Initialize the global connection pool."""
    pool = get_connection_pool()
    await pool.initialize()


async def close_pool() -> None:
    """Close the global connection pool."""
    global _connection_pool

    if _connection_pool is not None:
        await _connection_pool.close()
        _connection_pool = None
