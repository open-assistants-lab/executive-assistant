import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    from src.config import settings as settings_module
    from src.llm import factory as factory_module
    from src.observability import langfuse as langfuse_module
    from src.storage import postgres as postgres_module

    settings_module._settings = None
    factory_module._factory = None
    langfuse_module._langfuse_client = None
    postgres_module._postgres_connection = None

    original_env = os.environ.copy()
    env_vars_to_clear = [
        k
        for k in os.environ
        if k.startswith(
            (
                "OPENAI_",
                "ANTHROPIC_",
                "GOOGLE_",
                "AZURE_",
                "GROQ_",
                "LANGFUSE_",
                "DATABASE_",
                "DEFAULT_",
                "SUMMARIZATION_",
                "TELEGRAM_",
                "APP_",
                "DATA_PATH",
            )
        )
    ]
    for key in env_vars_to_clear:
        del os.environ[key]
    yield
    os.environ.clear()
    os.environ.update(original_env)
    settings_module._settings = None
    factory_module._factory = None
    langfuse_module._langfuse_client = None
    postgres_module._postgres_connection = None


@pytest.fixture
def mock_env_with_openai(clean_env: None) -> dict[str, str]:
    env = {
        "OPENAI_API_KEY": "sk-test-key-12345",
        "DEFAULT_MODEL": "openai/gpt-4o",
        "SUMMARIZATION_MODEL": "openai/gpt-4o-mini",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def mock_env_with_anthropic(clean_env: None) -> dict[str, str]:
    env = {
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "DEFAULT_MODEL": "anthropic/claude-3-5-sonnet-20241022",
        "SUMMARIZATION_MODEL": "anthropic/claude-3-5-haiku-20241022",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def mock_env_with_multiple_providers(clean_env: None) -> dict[str, str]:
    env = {
        "OPENAI_API_KEY": "sk-openai-key",
        "ANTHROPIC_API_KEY": "sk-ant-key",
        "GOOGLE_API_KEY": "google-key",
        "GROQ_API_KEY": "gsk-groq-key",
        "DEFAULT_MODEL": "openai/gpt-4o",
        "SUMMARIZATION_MODEL": "groq/llama-3.3-70b-versatile",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def mock_env_with_langfuse(clean_env: None) -> dict[str, str]:
    env = {
        "OPENAI_API_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test",
        "LANGFUSE_SECRET_KEY": "sk-test",
        "LANGFUSE_HOST": "https://cloud.langfuse.com",
        "LANGFUSE_ENABLED": "true",
        "DEFAULT_MODEL": "openai/gpt-4o",
        "SUMMARIZATION_MODEL": "openai/gpt-4o-mini",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def temp_data_path(tmp_path: Path) -> Path:
    data_path = tmp_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    return data_path


@pytest.fixture
def temp_user_path(temp_data_path: Path) -> Path:
    user_path = temp_data_path / "users" / "test-user-123"
    user_path.mkdir(parents=True, exist_ok=True)
    return user_path


# =============================================================================
# Middleware Test Fixtures
# =============================================================================

@pytest.fixture
def middleware_config():
    """Default middleware configuration for testing."""
    from src.config.middleware_settings import MiddlewareConfig
    return MiddlewareConfig()


@pytest.fixture
def mock_memory_store(temp_user_path: Path):
    """In-memory SQLite store for testing."""
    from src.memory import MemoryStore
    return MemoryStore(user_id="test-user", data_path=temp_user_path)


@pytest.fixture
def mock_memory_store_with_memories(mock_memory_store):
    """Memory store populated with test memories."""
    from src.memory import MemoryCreate, MemoryType, MemorySource

    memories = [
        MemoryCreate(
            title="User prefers async communication",
            type=MemoryType.PREFERENCE,
            narrative="User prefers asynchronous communication over real-time meetings for non-urgent matters.",
            facts=["Prefers Slack over Zoom", "Responds faster to written messages"],
            concepts=["communication", "productivity", "async"],
            confidence=0.9,
            source=MemorySource.EXPLICIT,
        ),
        MemoryCreate(
            title="VP Engineering based in SF",
            type=MemoryType.PROFILE,
            narrative="User is VP of Engineering based in San Francisco, PST timezone.",
            facts=["VP Engineering", "Based in San Francisco", "PST timezone"],
            concepts=["role", "location", "timezone"],
            confidence=0.95,
            source=MemorySource.EXPLICIT,
        ),
        MemoryCreate(
            title="Low confidence insight",
            type=MemoryType.INSIGHT,
            narrative="User might be stressed before board meetings (low confidence).",
            confidence=0.5,
            source=MemorySource.INFERRED,
        ),
    ]

    for memory in memories:
        mock_memory_store.add(memory)

    return mock_memory_store


@pytest.fixture
def mock_model_request():
    """Mock model request for testing middleware."""
    from langchain.agents.middleware import ModelRequest
    from langchain.messages import HumanMessage, SystemMessage
    from langchain_core.language_models import BaseChatModel

    # Create a mock model
    class MockModel(BaseChatModel):
        def __init__(self):
            super().__init__()

    @property
    def _llm_type(self) -> str:
        return "mock-model"

    def _generate(self, *args, **kwargs):
        from langchain_core.messages import AIMessage
        return AIMessage(content="Mock response")

    @property
    def model_version(self):
        return "mock-v1"

    model = MockModel()

    return ModelRequest(
        model=model,
        messages=[
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="What do you remember about me?"),
        ],
        system_message=SystemMessage(content="You are a helpful assistant."),
    )


@pytest.fixture
def mock_handler():
    """Mock handler function for testing middleware."""
    async def handler(request):
        from langchain.agents.middleware import ModelResponse
        from langchain.messages import AIMessage

        return ModelResponse(
            messages=[AIMessage(content="Test response")],
        )

    # For sync calls in middleware, provide a sync wrapper
    handler.sync = lambda req: handler(req)

    return handler


@pytest.fixture
def mock_agent_state():
    """Mock agent state for testing middleware."""
    from langchain.messages import HumanMessage, AIMessage

    class MockAgentState(dict):
        def __init__(self):
            super().__init__()
            self["messages"] = [
                HumanMessage(content="Test message"),
                AIMessage(content="Test response"),
            ]
            self["user_id"] = "test-user"

        def get(self, key, default=None):
            return super().get(key, default)

    return MockAgentState()


@pytest.fixture
def mock_runtime():
    """Mock runtime for testing middleware."""
    return MagicMock()


# =============================================================================
# HTTP Integration Test Fixtures
# =============================================================================

@pytest.fixture
async def http_client_with_agent():
    """HTTP client with real agent server for integration testing.

    This fixture starts a real agent server and provides an HTTP client.
    Tests can make real HTTP requests to test middleware behavior.
    """
    import subprocess
    import time
    import asyncio
    from httpx import AsyncClient, ASGITransport
    from src.api.app import app

    # Start the agent server in background
    # Note: In production, you might want to use a test database
    # For now, we'll use the ASGI test client instead of spawning a process

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
async def http_client_with_running_server():
    """HTTP client with actually running server (slower but more realistic).

    This starts a real server process for testing.
    Use only when necessary as it's slower than ASGI test client.
    """
    import subprocess
    import time
    import signal
    from httpx import AsyncClient

    # Start server in background
    # Note: This requires the server to be startable via CLI
    proc = subprocess.Popen(
        ["uv", "run", "ken", "serve", "--port", "8765"],
        cwd="/Users/eddy/Developer/Langgraph/executive-assistant",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    max_wait = 10
    for i in range(max_wait):
        try:
            import httpx
            test_client = httpx.AsyncClient()
            await test_client.get("http://localhost:8765/health")
            await test_client.aclose()
            break
        except Exception:
            time.sleep(1)
            if i == max_wait - 1:
                # Cleanup and skip test
                proc.terminate()
                proc.wait()
                pytest.skip("Could not start server")

    try:
        async with AsyncClient(base_url="http://localhost:8765") as client:
            yield client
    finally:
        # Cleanup: terminate server
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)


@pytest.fixture
def sample_conversation_for_memory():
    """Sample conversation messages for testing memory extraction."""
    return [
        "Remember that I prefer asynchronous communication over real-time meetings",
        "I'm the VP of Engineering based in San Francisco",
        "My team consists of Sarah (frontend), Mike (backend), and Lisa (design)",
        "We're using React, TypeScript, and Python for our tech stack",
        "My budget for Q1 is $50,000",
    ]


@pytest.fixture
def long_conversation_for_summarization():
    """Long conversation to trigger summarization (8000+ tokens)."""
    messages = []
    for i in range(50):
        messages.extend([
            f"Message {i}: Please remember that Project X has a deadline next Friday",
            f"Message {i}: The stakeholder meeting is scheduled for Monday at 10 AM",
            f"Message {i}: We need to finalize the budget proposal by end of day",
            f"Message {i}: Sarah is working on the frontend components using React",
            f"Message {i}: Mike is handling the backend API with Python and FastAPI",
        ])
    return messages

