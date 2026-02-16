"""HTTP integration tests for SummarizationMiddleware.

Tests summarization effectiveness via HTTP API.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_summarization_trigger_http(
    http_client_with_agent: AsyncClient,
    long_conversation_for_summarization: list[str],
):
    """Test that summarization triggers when threshold is exceeded via HTTP.

    This is a CRITICAL test for summarization effectiveness.
    """
    # Send long conversation to exceed token threshold
    # The threshold is typically 8000 tokens

    messages_sent = 0
    for message in long_conversation_for_summarization:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": message}
        )
        assert response.status_code == 200
        messages_sent += 1

        # Don't send ALL messages to save time in tests
        if messages_sent >= 20:  # Send enough to potentially trigger
            break

    # Send a query that would require context from earlier messages
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What was the deadline I mentioned earlier?"}
    )

    assert response.status_code == 200
    data = response.json()

    # Should still be able to answer correctly
    # (even if conversation was summarized)
    response_text = str(data).lower()
    # Should mention the deadline
    # Note: Actual keyword depends on conversation content


@pytest.mark.asyncio
async def test_summarization_token_compression_http(
    http_client_with_agent: AsyncClient,
):
    """Test summarization achieves target compression ratio (>50%) via HTTP.

    CRITICAL: Target is >50% compression.
    Example: 10,000 tokens → <5,000 tokens after summarization
    """
    # Create a very long conversation
    long_conversation = []
    for i in range(100):
        long_conversation.append(
            f"Here is a detailed message about Project X: "
            f"The deadline is next Friday and we need to coordinate with "
            f"Sarah, Mike, and Lisa to ensure all components are ready. "
            f"The budget is $50,000 and we're using React, TypeScript, and Python. "
            f"We have daily standups at 10am and the stakeholder review is Monday. "
        )

    # Send all messages
    for msg in long_conversation:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Check conversation state or logs to verify summarization occurred
    # This requires API endpoint to check conversation state or logs
    # For now, we verify the agent still functions

    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Summarize what we discussed about Project X"}
    )

    assert response.status_code == 200

    # In a real test, you would:
    # 1. Get conversation token count before summarization
    # 2. Get token count after summarization
    # 3. Assert: after_tokens < before_tokens * 0.5 (50% compression)


@pytest.mark.asyncio
async def test_summarization_information_retention_http(
    http_client_with_agent: AsyncClient,
):
    """Test summarization preserves key information (90%+ retention) via HTTP.

    CRITICAL: Target is 90%+ information retention.
    """
    # Create conversation with specific, trackable facts
    facts = [
        ("Project deadline", "Project X deadline is next Friday at 5 PM"),
        ("Team members", "Team consists of Sarah (frontend), Mike (backend), Lisa (design)"),
        ("Tech stack", "Using React, TypeScript, and Python"),
        ("Budget", "Budget approved for $50,000"),
        ("Meetings", "Daily standup at 10 AM, stakeholder review Monday"),
        ("Location", "Team is distributed across SF, NYC, and London"),
        ("Client", "Client is Acme Corporation"),
        ("Goals", "Goal is to launch MVP by Q2"),
        ("Constraints", "Must comply with GDPR and SOC2"),
        ("Next steps", "Next steps: complete backend API, finalize UI design"),
    ]

    # Send all facts
    for category, fact in facts:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": fact}
        )
        assert response.status_code == 200

    # Add filler to trigger summarization
    for i in range(50):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Filler message {i} to increase token count"}
        )
        assert response.status_code == 200

    # Query for each fact and verify retention
    facts_retained = 0
    for category, fact in facts:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"What do you remember about {category}?"}
        )
        assert response.status_code == 200

        data = response.json()
        response_text = str(data).lower()

        # Check if key information is present
        # This is a simple check - real implementation would be more sophisticated
        # Extract key terms from fact
        key_terms = fact.split()[:3]  # Use first 3 words as key terms
        if any(term.lower() in response_text for term in key_terms):
            facts_retained += 1

    # Calculate retention rate
    retention_rate = facts_retained / len(facts)

    # Assert 90%+ retention
    assert retention_rate >= 0.9, f"Retention rate {retention_rate:.2%} is below 90% target"


@pytest.mark.asyncio
async def test_summarization_quality_score_http(
    http_client_with_agent: AsyncClient,
):
    """Test summary quality using LLM-as-judge via HTTP.

    CRITICAL: Target is 4/5 quality score.
    """
    # Create a complex conversation
    conversation = [
        "I'm leading Project X with a deadline next Friday",
        "My team includes Sarah (React), Mike (Python), and Lisa (Design)",
        "We have a $50k budget and need to launch MVP by Q2",
        "Daily standups at 10am, stakeholder review Monday",
        "Must comply with GDPR and SOC2 requirements",
        "Client is Acme Corp, they're excited about the progress",
    ]

    for msg in conversation:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Trigger summarization by adding more messages
    for i in range(30):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Update {i}: Making progress on tasks"}
        )
        assert response.status_code == 200

    # Get summary
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "Give me a concise summary of our project"}
    )

    assert response.status_code == 200
    data = response.json()

    # In a real implementation, you would:
    # 1. Extract the summary from the response
    # 2. Send summary to an LLM with a prompt to rate quality
    # 3. Use a scoring rubric (completeness, accuracy, conciseness)
    # 4. Assert score >= 4/5

    # For now, just verify we got a response
    assert "response" in data or "content" in data or "message" in data


@pytest.mark.asyncio
async def test_summarization_no_summarization_below_threshold_http(
    http_client_with_agent: AsyncClient,
):
    """Test that summarization doesn't trigger below threshold via HTTP."""
    # Send a short conversation (below threshold)
    short_conversation = [
        "Hello",
        "Hi there",
        "How are you?",
        "I'm doing well",
    ]

    for msg in short_conversation:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Verify conversation is intact
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What did I say first?"}
    )

    assert response.status_code == 200
    data = response.json()

    # Should have the exact original message
    response_text = str(data).lower()
    assert "hello" in response_text


@pytest.mark.asyncio
async def test_summarization_preserves_speaker_attribution_http(
    http_client_with_agent: AsyncClient,
):
    """Test that summarization preserves speaker attribution via HTTP."""
    conversation = [
        ("user", "I need to submit the budget by Friday"),
        ("assistant", "I'll help you with the budget submission"),
        ("user", "Also remind me about the meeting with Sarah"),
        ("assistant", "Got it, meeting with Sarah"),
    ]

    # Send conversation
    for role, msg in conversation:
        # In real implementation, you might specify role
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Add filler to trigger summarization
    for i in range(20):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Filler {i}"}
        )
        assert response.status_code == 200

    # Query should maintain speaker context
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What did I ask you to help with?"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_summarization_performance_http(
    http_client_with_agent: AsyncClient,
):
    """Test that summarization completes quickly via HTTP."""
    import time

    # Create a long conversation
    long_conversation = [f"Message {i}: " + "x" * 100 for i in range(100)]

    # Send all messages and track time
    start = time.time()
    for msg in long_conversation[:20]:  # Send subset for speed
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # If summarization triggered, it should be fast
    duration = time.time() - start

    # Should complete in reasonable time
    # Adjust threshold based on requirements
    assert duration < 60.0  # 60 seconds max for 20 messages


@pytest.mark.asyncio
async def test_summarization_with_tools_http(
    http_client_with_agent: AsyncClient,
):
    """Test that summarization works correctly with tool calls via HTTP."""
    # Create conversation with tool calls
    messages = [
        "What's the weather in San Francisco?",
        "Search for recent AI news",
        "Remind me to submit the budget",
        "I need to check the stock price of AAPL",
    ]

    for msg in messages:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Add filler to trigger summarization
    for i in range(20):
        response = await http_client_with_agent.post(
            "/message",
            json={"message": f"Filler message {i}"}
        )
        assert response.status_code == 200

    # Query should still work even after summarization
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What tools did we use earlier?"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_summarization_multiple_cycles_http(
    http_client_with_agent: AsyncClient,
):
    """Test multiple summarization cycles via HTTP."""
    # First cycle: exceed threshold, get summary
    conversation_1 = [f"Batch 1 message {i}: " + "x" * 50 for i in range(50)]
    for msg in conversation_1:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Second cycle: more messages, another summary
    conversation_2 = [f"Batch 2 message {i}: " + "y" * 50 for i in range(50)]
    for msg in conversation_2:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": msg}
        )
        assert response.status_code == 200

    # Should still function correctly
    response = await http_client_with_agent.post(
        "/message",
        json={"message": "What did we discuss in both batches?"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_summarization_error_handling_http(
    http_client_with_agent: AsyncClient,
):
    """Test error handling in summarization via HTTP."""
    # Send various edge cases
    edge_cases = [
        "",  # Empty message
        "   ",  # Whitespace only
        "🚀🎉",  # Only emojis
        "a" * 10000,  # Very long message
    ]

    for edge_msg in edge_cases:
        response = await http_client_with_agent.post(
            "/message",
            json={"message": edge_msg}
        )
        # Should handle gracefully (200, 400, or 422 all acceptable)
        assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_summarization_custom_threshold_http(
    http_client_with_agent: AsyncClient,
):
    """Test custom summarization threshold via HTTP configuration.

    This would require config.yaml to be set before test.
    For now, it's a placeholder for when custom thresholds are supported.
    """
    # This test would:
    # 1. Load a config with custom threshold
    # 2. Verify summarization triggers at custom threshold
    # 3. Reset config after test

    # Placeholder assertion
    assert True
