"""Main entry point for running Cassey bot."""

import asyncio
import os
import signal
import sys
from typing import Any

from cassey.config import create_model, settings
from cassey.logging import configure_logging
from cassey.tools.registry import get_all_tools
from cassey.storage.checkpoint import get_async_checkpointer
from cassey.storage.user_registry import UserRegistry
from cassey.channels.telegram import TelegramChannel
from cassey.channels.http import HttpChannel
from cassey.agent.graph import create_graph
from cassey.agent.langchain_agent import create_langchain_agent
from cassey.agent.prompts import get_system_prompt
from cassey.scheduler import start_scheduler, stop_scheduler, register_notification_handler


def get_channels():
    """Get configured channels based on environment."""
    channels_str = os.getenv("CASSEY_CHANNELS", "telegram").lower()
    return [c.strip() for c in channels_str.split(",")]


async def main() -> None:
    """Start the Cassey bot."""
    configure_logging()
    # Create LLM model
    model = create_model()
    print(f" Using LLM provider: {settings.DEFAULT_LLM_PROVIDER}")

    # Load tools
    tools = await get_all_tools()
    print(f" Loaded {len(tools)} tools")

    # Create checkpointer
    checkpointer = await get_async_checkpointer()
    print(f" Checkpointer: {settings.CHECKPOINT_STORAGE}")

    runtime = settings.AGENT_RUNTIME.lower()
    fallback = settings.AGENT_RUNTIME_FALLBACK.lower() if settings.AGENT_RUNTIME_FALLBACK else None
    print(f" Agent runtime: {runtime}")

    agent_cache: dict[str, Any] = {}

    def build_agent(runtime_name: str, channel_name: str) -> Any:
        if runtime_name == "langchain":
            cache_key = f"langchain:{channel_name}"
            if cache_key not in agent_cache:
                system_prompt = get_system_prompt(channel_name)
                agent_cache[cache_key] = create_langchain_agent(
                    model=model,
                    tools=tools,
                    checkpointer=checkpointer,
                    system_prompt=system_prompt,
                )
            return agent_cache[cache_key]
        if runtime_name == "custom":
            if "custom" not in agent_cache:
                agent_cache["custom"] = create_graph(
                    model=model,
                    tools=tools,
                    checkpointer=checkpointer,
                )
            return agent_cache["custom"]
        raise ValueError(f"Unknown AGENT_RUNTIME: {runtime_name}")

    def get_agent(channel_name: str) -> tuple[Any, str]:
        try:
            return build_agent(runtime, channel_name), runtime
        except Exception as exc:
            if fallback and fallback != runtime:
                print(
                    f" Warning: failed to build runtime '{runtime}' ({exc}). "
                    f"Falling back to '{fallback}'."
                )
                return build_agent(fallback, channel_name), fallback
            raise

    # Create user registry (for audit logging)
    registry = UserRegistry(conn_string=settings.POSTGRES_URL)

    # Start the reminder scheduler
    await start_scheduler()
    print(" Reminder scheduler started")

    # Determine which channels to run
    enabled_channels = get_channels()
    active_channels = []

    for channel_name in enabled_channels:
        if channel_name == "telegram":
            agent, agent_runtime = get_agent("telegram")
            channel = TelegramChannel(agent=agent, runtime=agent_runtime)
            channel.registry = registry

            # Register notification handler for reminders
            async def telegram_notification_handler(thread_ids, message):
                """Send reminder notification via Telegram."""
                for thread_id in thread_ids:
                    # Extract chat_id from thread_id (format: telegram:chat_id)
                    if thread_id.startswith("telegram:"):
                        chat_id = thread_id.split(":", 1)[1]
                        await channel.send_message(chat_id, f"🔔 Reminder: {message}")

            register_notification_handler("telegram", telegram_notification_handler)

            active_channels.append(channel)
            print(" Telegram channel created")
        elif channel_name == "http":
            agent, agent_runtime = get_agent("http")
            channel = HttpChannel(
                agent=agent,
                host=os.getenv("HTTP_HOST", "0.0.0.0"),
                port=int(os.getenv("HTTP_PORT", "8000")),
                runtime=agent_runtime,
            )
            channel.registry = registry

            # Register notification handler for reminders
            async def http_notification_handler(thread_ids, message):
                """HTTP channel doesn't support push notifications yet."""
                # HTTP clients would need to poll or use websockets
                print(f"HTTP reminder notification (not delivered): {message}")

            register_notification_handler("http", http_notification_handler)

            active_channels.append(channel)
            print(f" HTTP channel created (port {channel.port})")
        else:
            print(f" Unknown channel: {channel_name}")

    if not active_channels:
        print(" Error: No valid channels configured")
        await stop_scheduler()
        sys.exit(1)

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\nShutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start all channels
    print("\nCassey is starting...")
    tasks = []
    for channel in active_channels:
        tasks.append(asyncio.create_task(channel.start()))

    try:
        print(f" Bot is running. Channels: {', '.join(enabled_channels)}. Press Ctrl+C to stop.")
        await shutdown_event.wait()
    finally:
        for channel in active_channels:
            await channel.stop()
        await stop_scheduler()
        print(" Bot stopped")


def run_main() -> None:
    """Synchronous entry point for console script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run_main()
