"""Unit tests for user registry."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from cassey.storage.user_registry import UserRegistry, MessageLog, ConversationLog


@pytest.fixture
def mock_pool():
    """Create a mock connection pool."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = MagicMock(return_value=conn)
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=123)
    conn.close = AsyncMock()

    # Mock transaction() to return an async context manager
    class TransactionMock:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    conn.transaction = lambda: TransactionMock()
    return conn


@pytest.fixture
def user_registry():
    """Create an UserRegistry instance."""
    return UserRegistry(conn_string="postgresql://test:test@localhost/test")


class TestUserRegistry:
    """Test UserRegistry class."""

    @pytest.mark.asyncio
    async def test_log_human_message(self, user_registry, mock_connection):
        """Test logging a human message."""
        with patch("asyncpg.connect", AsyncMock(return_value=mock_connection)):
            msg_id = await user_registry.log_message(
                conversation_id="test_conv",
                user_id="user_123",
                channel="telegram",
                message=HumanMessage(content="Hello"),
                message_id="msg_123",
            )

            assert msg_id == 123

    @pytest.mark.asyncio
    async def test_log_ai_message(self, user_registry, mock_connection):
        """Test logging an AI message."""
        mock_connection.fetchval = AsyncMock(return_value=456)

        with patch("asyncpg.connect", AsyncMock(return_value=mock_connection)):
            msg_id = await user_registry.log_message(
                conversation_id="test_conv",
                user_id="user_123",
                channel="telegram",
                message=AIMessage(content="Hi there!"),
            )

            assert msg_id == 456

    def test_get_role_human(self, user_registry):
        """Test role mapping for human message."""
        role = user_registry._get_role(HumanMessage(content="test"))
        assert role == "human"

    def test_get_role_assistant(self, user_registry):
        """Test role mapping for AI message."""
        role = user_registry._get_role(AIMessage(content="test"))
        assert role == "assistant"

    def test_get_role_system(self, user_registry):
        """Test role mapping for system message."""
        from langchain_core.messages import SystemMessage
        role = user_registry._get_role(SystemMessage(content="test"))
        assert role == "system"

    def test_get_content_human(self, user_registry):
        """Test content extraction from human message."""
        content = user_registry._get_content(HumanMessage(content="Hello"))
        assert content == "Hello"

    def test_get_content_empty(self, user_registry):
        """Test content extraction from empty message."""
        content = user_registry._get_content(HumanMessage(content=""))
        assert content == ""

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, user_registry):
        """Test getting conversation history."""
        now = datetime.now()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {
                "id": 1,
                "conversation_id": "test_conv",
                "message_id": "msg_1",
                "role": "human",
                "content": "Hello",
                "metadata": None,
                "created_at": now,
                "token_count": None,
            }
        ])
        conn.close = AsyncMock()

        with patch("asyncpg.connect", AsyncMock(return_value=conn)):
            history = await user_registry.get_conversation_history("test_conv")

            assert len(history) == 1
            assert history[0].role == "human"
            assert history[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_get_user_conversations(self, user_registry):
        """Test getting user conversations."""
        now = datetime.now()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[
            {
                "conversation_id": "test_conv",
                "user_id": "user_123",
                "channel": "telegram",
                "created_at": now,
                "updated_at": now,
                "message_count": 5,
                "status": "active",
            }
        ])
        conn.close = AsyncMock()

        with patch("asyncpg.connect", AsyncMock(return_value=conn)):
            conversations = await user_registry.get_user_conversations("user_123")

            assert len(conversations) == 1
            assert conversations[0].message_count == 5

    @pytest.mark.asyncio
    async def test_get_message_count(self, user_registry):
        """Test getting message count with filters."""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=42)
        conn.close = AsyncMock()

        with patch("asyncpg.connect", AsyncMock(return_value=conn)):
            count = await user_registry.get_message_count(user_id="user_123")

            assert count == 42


class TestMessageLog:
    """Test MessageLog dataclass."""

    def test_message_log_creation(self):
        """Test creating a MessageLog instance."""
        log = MessageLog(
            id=1,
            conversation_id="test_conv",
            message_id="msg_1",
            role="human",
            content="Hello",
            metadata={},
            created_at=datetime.now(),
            token_count=None,
        )

        assert log.id == 1
        assert log.role == "human"
        assert log.content == "Hello"


class TestConversationLog:
    """Test ConversationLog dataclass."""

    def test_conversation_log_creation(self):
        """Test creating a ConversationLog instance."""
        log = ConversationLog(
            conversation_id="test_conv",
            user_id="user_123",
            channel="telegram",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message_count=5,
            status="active",
        )

        assert log.conversation_id == "test_conv"
        assert log.message_count == 5
