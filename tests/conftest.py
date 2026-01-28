"""Shared fixtures and configuration for pytest."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator, Generator

import pytest
import asyncpg

from executive_assistant.config import settings


# =============================================================================
# Asyncio Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# PostgreSQL Fixtures
# =============================================================================

@pytest.fixture
async def db_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Create a database connection for testing.

    This fixture provides a real PostgreSQL connection for integration tests.
    Tests should clean up any data they create.
    """
    conn = await asyncpg.connect(settings.POSTGRES_URL)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def clean_test_data(db_conn: asyncpg.Connection) -> AsyncGenerator[None, None]:
    """Clean up test data before and after each test.

    This fixture deletes test data (thread_id starting with 'test_')
    from relevant tables.
    """
    # Ensure legacy user_id columns are removed for thread-only schema
    try:
        await db_conn.execute("ALTER TABLE scheduled_flows DROP COLUMN IF EXISTS user_id")
    except Exception:
        pass
    try:
        await db_conn.execute("ALTER TABLE reminders DROP COLUMN IF EXISTS user_id")
    except Exception:
        pass
    # Ensure thread_id column exists on reminders (legacy schemas may lack it)
    try:
        await db_conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'reminders'
                      AND column_name = 'thread_id'
                ) THEN
                    ALTER TABLE reminders ADD COLUMN thread_id VARCHAR(255);
                END IF;
            END $$;
            """
        )
    except Exception:
        pass
    # Ensure tdb_paths table exists for integration tests
    try:
        await db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tdb_paths (
                tdb_path TEXT NOT NULL,
                thread_id VARCHAR(255) NOT NULL,
                channel VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )
    except Exception:
        pass

    # Clean up before test
    await db_conn.execute("DELETE FROM scheduled_flows WHERE thread_id LIKE 'test_%'")

    yield

    # Clean up after test
    await db_conn.execute("DELETE FROM scheduled_flows WHERE thread_id LIKE 'test_%'")


# =============================================================================
# Mock Database Fixtures
# =============================================================================

@pytest.fixture
def mock_conn() -> AsyncMock:
    """Create a mock database connection."""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.transaction = MagicMock()
    conn.transaction.__aenter__ = AsyncMock()
    conn.transaction.__aexit__ = AsyncMock()
    return conn


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================

@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    """Create a temporary root directory for tests."""
    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


# =============================================================================
# Settings Patches
# =============================================================================

@pytest.fixture
def temp_settings(tmp_path: Path):
    """Patch settings with temporary paths."""
    from unittest.mock import patch

    temp_root = tmp_path / "data"
    temp_root.mkdir(parents=True, exist_ok=True)

    patches = {
        "USERS_ROOT": temp_root / "users",
        "SHARED_ROOT": temp_root / "shared",
    }

    # Create directories
    for path in patches.values():
        path.mkdir(parents=True, exist_ok=True)

    with patch.multiple(settings, **patches):
        yield settings


# =============================================================================
# Context Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
def clean_context() -> Generator[None, None, None]:
    """Clean up context variables before and after each test."""
    from executive_assistant.storage.thread_storage import clear_thread_id, set_thread_id

    # Clean before
    clear_thread_id()
    set_thread_id("")

    yield

    # Clean after
    clear_thread_id()
    set_thread_id("")
