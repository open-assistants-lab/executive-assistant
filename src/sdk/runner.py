"""SDK Agent Runner — creates and runs AgentLoop with proper wiring.

This is the bridge between the HTTP layer and the SDK AgentLoop.
It handles:
  - Creating LLM provider from config
  - Loading SDK-native tools (no more LangChain adapter)
  - Assembling SDK middlewares (memory, skill, summarization)
  - Converting between WS protocol messages and StreamChunks
  - Thread-safe per-user agent instances
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.app_logging import get_logger
from src.config import get_settings
from src.sdk.loop import AgentLoop, Interrupt
from src.sdk.messages import Message, StreamChunk
from src.sdk.middleware_memory import MemoryMiddleware
from src.sdk.middleware_skill import SkillMiddleware
from src.sdk.middleware_summarization import SummarizationMiddleware
from src.sdk.native_tools import get_native_tools
from src.sdk.providers.factory import create_model_from_config

logger = get_logger()

_loop_cache: dict[str, AgentLoop] = {}
_loop_lock = asyncio.Lock()


def _get_system_prompt(user_id: str) -> str:
    settings = get_settings()
    base_prompt = getattr(settings.agent, "system_prompt", "You are a helpful executive assistant.")
    return base_prompt + f"\n\nuser_id: {user_id}"


def _get_interrupt_tools() -> set[str]:
    settings = get_settings()
    interrupt_on: set[str] = set()
    if getattr(settings.filesystem, "enabled", True):
        interrupt_on.add("files_delete")
    return interrupt_on


async def create_sdk_loop(user_id: str) -> AgentLoop:
    """Create an AgentLoop for a user with all wiring.

    All tools are now SDK-native (from src.sdk.native_tools).
    No more LangChain adapter needed.
    """
    settings = get_settings()
    model_str = getattr(settings.agent, "model", "ollama:minimax-m2.5")

    provider = create_model_from_config(model_str)

    tools = get_native_tools()

    logger.info("sdk_runner.tools_loaded", {"count": len(tools)}, user_id=user_id)

    summary_config = settings.memory.summarization

    middlewares: list[Any] = []

    if summary_config.enabled:
        middlewares.append(
            SummarizationMiddleware(
                trigger_tokens=summary_config.trigger_tokens,
                keep_tokens=summary_config.keep_tokens,
                model=model_str,
            )
        )

    middlewares.append(SkillMiddleware(system_dir="src/skills", user_id=user_id))
    middlewares.append(MemoryMiddleware(user_id=user_id))

    loop = AgentLoop(
        provider=provider,
        tools=tools,
        system_prompt=_get_system_prompt(user_id),
        middlewares=middlewares,
        interrupt_on=_get_interrupt_tools(),
    )

    return loop


async def get_sdk_loop(user_id: str) -> AgentLoop:
    """Get or create an AgentLoop for a user (cached)."""
    async with _loop_lock:
        if user_id not in _loop_cache:
            _loop_cache[user_id] = await create_sdk_loop(user_id)
            logger.info("sdk_runner.loop_created", {"user_id": user_id}, user_id=user_id)
        return _loop_cache[user_id]


def _messages_from_conversation(messages: list[Any]) -> list[Message]:
    """Convert conversation store messages to SDK Messages."""
    sdk_messages: list[Message] = []
    for m in messages:
        role = getattr(m, "role", "user")
        content = getattr(m, "content", "")
        if role == "user":
            sdk_messages.append(Message.user(content))
        elif role == "summary":
            sdk_messages.append(Message.user(f"[SUMMARY OF PREVIOUS CONVERSATION]\n{content}"))
        elif role == "system":
            sdk_messages.append(Message.system(content))
        else:
            sdk_messages.append(Message.assistant(content))
    return sdk_messages


async def run_sdk_agent(
    user_id: str,
    messages: list[Message],
) -> list[Message]:
    """Run the SDK agent loop to completion.

    Args:
        user_id: User identifier.
        messages: Conversation history as SDK Messages.

    Returns:
        Final message list from the agent.
    """
    loop = await get_sdk_loop(user_id)
    try:
        result = await loop.run(messages)
        return result
    except Interrupt:
        raise
    except Exception as e:
        logger.error("sdk_runner.run_error", {"error": str(e)}, user_id=user_id)
        raise


async def run_sdk_agent_stream(
    user_id: str,
    messages: list[Message],
) -> Any:
    """Run the SDK agent loop with streaming.

    Yields StreamChunk events that map directly to WS protocol messages.

    Args:
        user_id: User identifier.
        messages: Conversation history as SDK Messages.

    Yields:
        StreamChunk events.
    """
    loop = await get_sdk_loop(user_id)
    try:
        async for chunk in loop.run_stream(messages):
            yield chunk
    except Exception as e:
        logger.error("sdk_runner.stream_error", {"error": str(e)}, user_id=user_id)
        yield StreamChunk.error(message=str(e))


def reset_sdk_loop(user_id: str = "default") -> None:
    """Reset the SDK agent loop for a user."""
    if user_id in _loop_cache:
        del _loop_cache[user_id]
    logger.info("sdk_runner.loop_reset", {"user_id": user_id}, user_id=user_id)


def reset_all_sdk_loops() -> None:
    """Reset all cached agent loops."""
    _loop_cache.clear()
    logger.info("sdk_runner.all_loops_reset", {})
