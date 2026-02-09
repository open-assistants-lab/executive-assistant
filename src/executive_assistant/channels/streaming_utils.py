"""Streaming utilities for improved perceived performance.

This module provides utilities to stream responses with priority given to
important information and early status updates to improve perceived latency.
"""

import asyncio
from typing import AsyncIterator, Callable, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage
import time


async def stream_with_priority(
    stream_generator: AsyncIterator[str],
    send_status: Callable[[str], Any],
    send_chunk: Callable[[str], Any],
    first_chunk_timeout: float = 2.0,
) -> None:
    """
    Stream response with priority for better perceived performance.

    Strategy:
    1. Send immediate "thinking" status
    2. Get first chunk quickly (with timeout)
    3. If timeout, send "processing" status
    4. Stream remaining content normally
    5. Send completion status

    Args:
        stream_generator: The original stream generator
        send_status: Function to send status updates
        send_chunk: Function to send content chunks
        first_chunk_timeout: Seconds to wait for first chunk before sending secondary status
    """
    # Step 1: Send immediate thinking status
    try:
        await send_status("🤔 Thinking...")
    except Exception as e:
        # Log but don't fail if status send fails
        pass

    # Step 2 & 3: Get first chunk with timeout
    first_chunk_sent = False
    processing_status_sent = False

    try:
        async with asyncio.timeout(first_chunk_timeout):
            async for chunk in stream_generator:
                if not first_chunk_sent:
                    first_chunk_sent = True
                    # Clear thinking status implicitly by sending content
                await send_chunk(chunk)

    except TimeoutError:
        # Timeout - send processing status and continue
        if not first_chunk_sent:
            try:
                await send_status("🔄 Processing...")
                processing_status_sent = True
            except Exception:
                pass

        # Continue streaming remaining chunks
        async for chunk in stream_generator:
            if not first_chunk_sent:
                first_chunk_sent = True
            await send_chunk(chunk)

    # Step 5: Send completion status (handled by caller)
    if processing_status_sent:
        try:
            # Clear processing status
            await send_status("✅ Done")
        except Exception:
            pass


async def get_first_chunk_with_timeout(
    stream: AsyncIterator[BaseMessage],
    timeout: float = 2.0,
) -> Optional[str]:
    """
    Get first content chunk from stream with timeout.

    Args:
        stream: The message stream
        timeout: Seconds to wait for first chunk

    Returns:
        First chunk content or None if timeout
    """
    try:
        async with asyncio.timeout(timeout):
            async for msg in stream:
                if isinstance(msg, AIMessage):
                    content = getattr(msg, "content", None)
                    if content and str(content).strip():
                        return str(content)
    except TimeoutError:
        return None

    return None


class StreamPriorityManager:
    """
    Manages prioritized streaming for multiple concurrent requests.

    Ensures that important updates (status, errors) are sent before
    large content chunks.
    """

    def __init__(self):
        self._pending_queues: dict[str, asyncio.Queue] = {}

    async def send_priority_first(
        self,
        conversation_id: str,
        content: str,
        priority: int = 0,
    ) -> None:
        """
        Send message with priority level.

        Lower priority number = sent first

        Args:
            conversation_id: Unique conversation identifier
            content: Message content to send
            priority: Priority level (0=highest, 5=lowest)
        """
        if conversation_id not in self._pending_queues:
            self._pending_queues[conversation_id] = asyncio.Queue()

        await self._pending_queues[conversation_id].put((priority, content))

    async def get_next_chunk(
        self,
        conversation_id: str,
    ) -> Optional[str]:
        """
        Get next prioritized chunk for conversation.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Content chunk or None if queue empty
        """
        queue = self._pending_queues.get(conversation_id)
        if not queue or queue.empty():
            return None

        # Get all pending items and sort by priority
        items = []
        while not queue.empty():
            items.append(await queue.get())

        items.sort(key=lambda x: x[0])

        # Put back lower priority items
        for item in items[1:]:
            await queue.put(item)

        return items[0][1] if items else None

    def clear_conversation(self, conversation_id: str) -> None:
        """Clear pending chunks for a conversation."""
        self._pending_queues.pop(conversation_id, None)


# Singleton instance
_stream_priority_manager = StreamPriorityManager()


def get_stream_priority_manager() -> StreamPriorityManager:
    """Get the singleton stream priority manager."""
    return _stream_priority_manager
