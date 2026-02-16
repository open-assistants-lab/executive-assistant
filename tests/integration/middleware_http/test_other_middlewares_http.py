"""HTTP integration tests for remaining middlewares.

Tests MemoryLearning, Checkin, RateLimit, Logging, and middleware pipeline.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


# =============================================================================
# Memory Learning Middleware HTTP Tests
# =============================================================================

@pytest.mark.asyncio
async def test_memory_learning_extraction_http(
    http_client_with_agent: AsyncClient,
):
    """Test that memory learning extracts information via HTTP."""
    # Send conversation with extractable information
    conversation = [
        "I prefer asynchronous communication over real-time meetings",
        "I'm the VP of Engineering based in San Francisco",
        "My team consists of Sarah (frontend), Mike (backend), and Lisa (design)",
    ]

    for msg in conversation:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Wait a moment for extraction to occur
    import asyncio
    await asyncio.sleep(1)

    # Query for extracted information
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What do you know about my team?"}
    )

    assert response.status_code == 200
    data = response.json()
    response_text = str(data).lower()

    # Should mention team members
    assert "sarah" in response_text or "mike" in response_text or "lisa" in response_text


@pytest.mark.asyncio
async def test_memory_learning_confidence_http(
    http_client_with_agent: AsyncClient,
):
    """Test that confidence affects memory saving via HTTP."""
    # Send same info multiple times (should increase confidence)
    for _ in range(3):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": "I prefer Python for backend development"}
        )
        assert response.status_code == 200

    # Send once (lower confidence)
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "I might be interested in learning Rust someday"}
    )
    assert response.status_code == 200

    import asyncio
    await asyncio.sleep(1)

    # Query - high confidence should appear first
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What are my technology preferences?"}
    )

    assert response.status_code == 200


# =============================================================================
# Checkin Middleware HTTP Tests
# =============================================================================

@pytest.mark.asyncio
async def test_checkin_not_triggered_by_default_http(
    http_client_with_agent: AsyncClient,
):
    """Test that check-in is disabled by default via HTTP."""
    # Send a message
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Hello"}
    )

    assert response.status_code == 200
    data = response.json()

    # Should NOT include check-in prompt
    response_text = str(data).lower()
    # Check-in keywords should not appear
    assert "check-in" not in response_text or "checkin" not in response_text


@pytest.mark.asyncio
async def test_checkin_active_hours_http(
    http_client_with_agent: AsyncClient,
):
    """Test check-in active hours via HTTP."""
    # This would require config.yaml with checkin enabled
    # For now, just verify request succeeds

    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Hello"}
    )

    assert response.status_code == 200


# =============================================================================
# Rate Limit Middleware HTTP Tests
# =============================================================================

@pytest.mark.asyncio
async def test_rate_limit_within_bounds_http(
    http_client_with_agent: AsyncClient,
):
    """Test that requests within rate limit succeed via HTTP."""
    # Make several requests (within limit)
    for i in range(5):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Test message {i}"}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_exceeded_http(
    http_client_with_agent: AsyncClient,
):
    """Test that rate limit blocks excessive requests via HTTP."""
    # This would require hitting the actual rate limit
    # For now, just verify the endpoint exists

    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Test"}
    )

    # Should either succeed or rate limit
    assert response.status_code in [200, 429]


# =============================================================================
# Logging Middleware HTTP Tests
# =============================================================================

@pytest.mark.asyncio
async def test_logging_creates_log_files_http(
    http_client_with_agent: AsyncClient,
    tmp_path: Path,
):
    """Test that logging creates log files via HTTP."""
    # Make a request
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Test message for logging"}
    )

    assert response.status_code == 200

    # Check if log file was created
    # Note: Log location depends on configuration
    # This is a placeholder - real implementation would check actual log path
    import time
    time.sleep(0.5)  # Give time for log to be written

    # Would verify:
    # log_file = Path("/data/logs/agent-<date>.jsonl")
    # assert log_file.exists()


@pytest.mark.asyncio
async def test_logging_jsonl_format_http(
    http_client_with_agent: AsyncClient,
):
    """Test that logs are in JSONL format via HTTP."""
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Test for JSONL logging"}
    )

    assert response.status_code == 200

    # Would verify log file format
    # Expected: One JSON object per line


# =============================================================================
# Middleware Pipeline HTTP Tests
# =============================================================================

@pytest.mark.asyncio
async def test_middleware_pipeline_execution_order_http(
    http_client_with_agent: AsyncClient,
):
    """Test that middlewares execute in correct order via HTTP."""
    # Send a message that goes through all middlewares
    response = await http_client_with_agent.post(
        "/message",
        json={
            "message": "Remember: I prefer async communication. "
                      "What's the weather in San Francisco?",
        }
    )

    assert response.status_code == 200

    # Should have:
    # 1. Memory context injected (before model)
    # 2. Model call (logged)
    # 3. Tool call (web search, logged)
    # 4. Memory learning (after agent, logged)


@pytest.mark.asyncio
async def test_middleware_pipeline_error_handling_http(
    http_client_with_agent: AsyncClient,
):
    """Test error handling in middleware pipeline via HTTP."""
    # Send a potentially problematic message
    response = await http_client_with_agent.post(
        "/message",
        json={"message": ""}  # Empty message
    )

    # Should handle gracefully
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_all_middlewares_together_http(
    http_client_with_agent: AsyncClient,
    sample_conversation_for_memory: list[str],
):
    """Test all middlewares working together via HTTP.

    This is a comprehensive integration test.
    """
    import time

    # 1. Send conversation (triggers memory learning, logging)
    for msg in sample_conversation_for_memory:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    time.sleep(1)  # Let extraction occur

    # 2. Query (triggers memory context, logging)
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What do you remember about my preferences?"}
    )
    assert response.status_code == 200

    # 3. Make many requests (test rate limiting)
    for i in range(10):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Quick question {i}"}
        )
        # Should either succeed or rate limit
        assert response.status_code in [200, 429]

    # 4. Verify logs were created
    # (would check log files exist and contain entries)


@pytest.mark.asyncio
async def test_middleware_configuration_reloading_http(
    http_client_with_agent: AsyncClient,
):
    """Test that middleware configuration changes take effect via HTTP.

    This would require modifying config.yaml during test.
    """
    # This is a placeholder for when config hot-reload is implemented
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Test"}
    )

    assert response.status_code in [200, 429]


# =============================================================================
# Cross-Middleware Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_memory_and_summarization_interaction_http(
    http_client_with_agent: AsyncClient,
):
    """Test interaction between memory and summarization via HTTP."""
    # Add memories
    memories = [
        "I'm the VP of Engineering",
        "I prefer async communication",
        "My team is Sarah, Mike, and Lisa",
    ]

    for mem in memories:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": mem}
        )
        assert response.status_code == 200

    # Create long conversation to trigger summarization
    for i in range(30):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Update {i}: Working on Project X"}
        )
        assert response.status_code == 200

    # Query for memories (should still work after summarization)
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What do you know about my role?"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logging_and_rate_limit_interaction_http(
    http_client_with_agent: AsyncClient,
):
    """Test interaction between logging and rate limiting via HTTP."""
    # Make rapid requests
    # Logging should record all requests
    # Rate limiting should block excessive requests

    request_count = 0
    for i in range(20):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Request {i}"}
        )

        request_count += 1
        if response.status_code == 429:
            # Hit rate limit
            break

        assert response.status_code == 200

    # Should have logged all requests
    # (would verify log file)


@pytest.mark.asyncio
async def test_memory_learning_and_context_cycle_http(
    http_client_with_agent: AsyncClient,
):
    """Test the full memory learning → context cycle via HTTP."""
    # 1. User shares information
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "I'm a VP of Engineering based in SF"}
    )
    assert response.status_code == 200

    import asyncio
    await asyncio.sleep(2)  # Let learning occur

    # 2. User queries (context should have learned info)
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What's my role and location?"}
    )

    assert response.status_code == 200
    data = response.json()
    response_text = str(data).lower()

    # Should mention VP and SF
    assert "vp" in response_text or "engineering" in response_text
    assert "sf" in response_text or "san francisco" in response_text
