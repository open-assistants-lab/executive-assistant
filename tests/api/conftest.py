"""Shared fixtures for API contract tests."""

import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CHECKPOINT_ENABLED", "false")
os.environ.setdefault("USER_ID", "test_api_user")


@pytest.fixture(scope="session")
def app():
    """Create FastAPI app for testing."""
    from src.http.main import app

    return app


@pytest.fixture(scope="session")
def client(app):
    """Create a TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user_id():
    """Return a unique test user ID."""
    return f"test_api_{os.getpid()}"


@pytest.fixture
def test_user_id_2():
    """Return a second test user ID for isolation tests."""
    return f"test_api_2_{os.getpid()}"


@pytest.fixture
def conversation_messages():
    """Sample messages for conversation tests."""
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What can you do?"},
        {"role": "assistant", "content": "I can help with many tasks."},
    ]
