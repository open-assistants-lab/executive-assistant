"""Database manager for Executive Assistant."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from src.config import get_settings

Base = declarative_base()


class DatabaseManager:
    """Manages database connections and checkpointer."""

    _instance: Optional["DatabaseManager"] = None
    _pool: Optional[asyncpg.Pool] = None
    _checkpointer: Optional[PostgresSaver] = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """Initialize database connections."""
        settings = get_settings()
        config = settings.database

        self._pool = await asyncpg.create_pool(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.name,
            min_size=1,
            max_size=config.pool_size,
        )

        # Create PostgresSaver for checkpointer
        self._checkpointer = PostgresSaver.from_conn_string(config.connection_string)
        await self._checkpointer.asetup()

    async def close(self) -> None:
        """Close database connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._checkpointer = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Get asyncpg pool."""
        if self._pool is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._pool

    @property
    def checkpointer(self) -> PostgresSaver:
        """Get LangGraph checkpointer."""
        if self._checkpointer is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._checkpointer

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database connection."""
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database transaction."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn


def get_database() -> DatabaseManager:
    """Get database manager singleton."""
    return DatabaseManager()


async def init_db() -> DatabaseManager:
    """Initialize database and return manager."""
    db = get_database()
    await db.initialize()
    return db
