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

    This fixture deletes test data (users/groups starting with 'test_')
    from relevant tables.
    """
    # Clean up before test
    await db_conn.execute("DELETE FROM user_aliases WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM group_members WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM groups WHERE group_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM users WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM scheduled_jobs WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM thread_groups WHERE thread_id LIKE 'test_%'")

    yield

    # Clean up after test
    await db_conn.execute("DELETE FROM user_aliases WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM group_members WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM groups WHERE group_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM users WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM scheduled_jobs WHERE user_id LIKE 'test_%'")
    await db_conn.execute("DELETE FROM thread_groups WHERE thread_id LIKE 'test_%'")


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


@pytest.fixture
def mock_get_db_conn(mock_conn: AsyncMock) -> AsyncMock:
    """Patch get_db_conn to return mock connection."""
    from unittest.mock import patch

    with patch("executive_assistant.storage.group_storage.get_db_conn", return_value=mock_conn):
        yield mock_conn


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================

@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    """Create a temporary root directory for tests."""
    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def temp_groups_root(tmp_path: Path) -> Path:
    """Create a temporary groups root for tests."""
    root = tmp_path / "data" / "groups"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def temp_kb_root(tmp_path: Path) -> Path:
    """Create a temporary KB root for tests."""
    root = tmp_path / "data" / "groups"
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
        "GROUPS_ROOT": temp_root / "groups",
        "USERS_ROOT": temp_root / "users",
        "FILES_ROOT": temp_root / "files",
        "DB_ROOT": temp_root / "db",
        "MEM_ROOT": temp_root / "mem",
        "KB_ROOT": temp_root / "kb",
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
    from executive_assistant.storage.group_storage import (
        set_group_id, clear_group_id,
        set_user_id, clear_user_id,
    )
    from executive_assistant.storage.file_sandbox import set_thread_id

    # Clean before
    clear_group_id()
    clear_user_id()
    set_thread_id("")

    yield

    # Clean after
    clear_group_id()
    clear_user_id()
    set_thread_id("")
