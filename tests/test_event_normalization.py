"""Tests for event shape normalization in channels."""

from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage

from cassey.channels.http import HttpChannel


def test_extract_messages_from_event_shapes():
    """Ensure we can extract messages from multiple event shapes."""
    channel = HttpChannel(agent=AsyncMock())
    message = AIMessage(content="hello")

    assert channel._extract_messages_from_event({"messages": [message]}) == [message]
    assert channel._extract_messages_from_event({"agent": {"messages": [message]}}) == [message]
    assert channel._extract_messages_from_event({"output": {"messages": [message]}}) == [message]
    assert channel._extract_messages_from_event({"final": {"messages": [message]}}) == [message]
    assert channel._extract_messages_from_event({"other": "value"}) == []
