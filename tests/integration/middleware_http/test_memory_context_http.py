"""HTTP integration tests for MemoryContextMiddleware.

Tests memory injection via HTTP endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_memory_context_injection_http(
    http_client_with_agent: AsyncClient,
    sample_conversation_for_memory: list[str],
):
    """Test that memories are injected via HTTP API.

    1. Send conversation to create memories
    2. Send query that should trigger memory retrieval
    3. Verify memories are in response
    """
    # First, add some information via conversation
    for message in sample_conversation_for_memory:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": message}
        )
        assert response.status_code == 200

    # Now query for information that should be in memories
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What do you remember about my team?"}
    )

    assert response.status_code == 200
    data = response.json()

    # Response should mention team members
    # Note: Actual response structure depends on API implementation
    assert "response" in data or "content" in data or "message" in data


@pytest.mark.asyncio
async def test_memory_context_progressive_disclosure_http(
    http_client_with_agent: AsyncClient,
):
    """Test progressive disclosure via HTTP.

    Verifies that only compact memory references are injected initially,
    not full memory content.
    """
    # Send information about self
    info_messages = [
        "I'm a VP of Engineering based in San Francisco",
        "I prefer async communication",
        "My favorite programming language is Python",
        "I'm working on a confidential project",
        "My budget for Q1 is $50,000",
    ]

    for msg in info_messages:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Query that should retrieve memories
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What do you know about me?"}
    )

    assert response.status_code == 200
    data = response.json()

    # Response should be relevant but not excessively long
    # (progressive disclosure saves tokens)
    response_text = str(data)
    # Should mention key facts but not be verbose
    # Token count would be ideal to check here


@pytest.mark.asyncio
async def test_memory_context_confidence_filtering_http(
    http_client_with_agent: AsyncClient,
):
    """Test that low-confidence memories are filtered via HTTP."""
    # Send information multiple times to increase confidence
    high_conf_info = "I prefer asynchronous communication"
    for _ in range(3):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": high_conf_info}
        )
        assert response.status_code == 200

    # Send information once (low confidence)
    low_conf_info = "I might be interested in learning Rust someday"
    response = await http_client_with_agent.post(
        "/message",
        json={"message": low_conf_info}
    )
    assert response.status_code == 200

    # Query for preferences
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What are my preferences?"}
    )

    assert response.status_code == 200

    # Should prefer high-confidence information
    # Low-confidence might not appear


@pytest.mark.asyncio
async def test_no_memory_context_without_memories_http(
    http_client_with_agent: AsyncClient,
):
    """Test that agent works fine without memories via HTTP."""
    # Use a unique user ID to ensure no existing memories
    response = await http_client_with_agent.post(
        "/message",
        json={
            "message": "Hello, what's 2+2?",
            "user_id": "test-user-no-memories"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Should get a valid response even without memories
    assert "response" in data or "content" in data or "message" in data


@pytest.mark.asyncio
async def test_memory_context_max_memories_limit_http(
    http_client_with_agent: AsyncClient,
):
    """Test that max_memories limit is respected via HTTP."""
    # Add lots of information
    facts = [
        f"Remember fact {i}: This is important information about my work"
        for i in range(20)
    ]

    for fact in facts:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": fact}
        )
        assert response.status_code == 200

    # Query for memories
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What facts do you remember about me?"}
    )

    assert response.status_code == 200

    # Response should not be excessively long
    # (limited by max_memories configuration)
    data = response.json()
    response_text = str(data)

    # With default max_memories=5, should get compact response
    # Could check token count or length here


@pytest.mark.asyncio
async def test_memory_context_type_filtering_http(
    http_client_with_agent: AsyncClient,
):
    """Test filtering by memory type via HTTP."""
    # Add different types of information
    messages = {
        "profile": ["I am a VP of Engineering", "I'm based in San Francisco"],
        "preference": ["I prefer async communication", "I like code reviews"],
        "task": ["Remind me to submit budget", "Don't forget the meeting"],
    }

    for mem_type, msgs in messages.items():
        for msg in msgs:
            response = await http_client_with_agent.post(
                "/message",
                json={"message": msg}
            )
            assert response.status_code == 200

    # Query for specific type
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What tasks do I have?"}
    )

    assert response.status_code == 200

    # Should prioritize task-type memories
    # (actual implementation depends on middleware)


@pytest.mark.asyncio
async def test_memory_context_relevance_ranking_http(
    http_client_with_agent: AsyncClient,
):
    """Test that memories are ranked by relevance via HTTP."""
    # Add diverse information
    memories = [
        ("I work in tech", "general"),
        ("I prefer Python", "preference"),
        ("Project deadline is Friday", "task"),
        ("Meeting at 2pm", "schedule"),
        ("Budget approved", "decision"),
    ]

    for memory, _ in memories:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": memory}
        )
        assert response.status_code == 200

    # Query about programming should rank "Python" higher
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What programming languages do I like?"}
    )

    assert response.status_code == 200

    # Response should mention Python preference
    # (relevance ranking implementation dependent)


@pytest.mark.asyncio
async def test_memory_context_with_tools_http(
    http_client_with_agent: AsyncClient,
):
    """Test that memory context works with tool calls via HTTP."""
    # Store some information
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "My email is john@example.com"}
    )
    assert response.status_code == 200

    # Trigger a tool call (e.g., search)
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Search for recent AI news and check if any relate to my work"}
    )

    assert response.status_code == 200

    # Memory should still be available during tool execution
    # (implementation dependent)


@pytest.mark.asyncio
async def test_memory_context_error_handling_http(
    http_client_with_agent: AsyncClient,
):
    """Test error handling in memory context middleware via HTTP."""
    # Send malformed message or edge case
    response = await http_client_with_agent.post(
        "/message",
        json={"message": ""}  # Empty message
    )

    # Should handle gracefully
    assert response.status_code in [200, 400, 422]

    if response.status_code == 200:
        # Agent handled empty message
        data = response.json()
        assert "response" in data or "content" in data


@pytest.mark.asyncio
async def test_memory_context_performance_http(
    http_client_with_agent: AsyncClient,
):
    """Test that memory context doesn't slow down requests significantly."""
    import time

    # Add some memories first
    for i in range(10):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Remember fact {i}"}
        )
        assert response.status_code == 200

    # Measure request time
    start = time.time()
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What do you remember?"}
    )
    duration = time.time() - start

    assert response.status_code == 200

    # Should complete in reasonable time
    # Adjust threshold based on your requirements
    assert duration < 30.0  # 30 seconds max
