"""Main entry point for running Cassey bot."""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Any

from cassey.config import create_model, settings
from cassey.config.loader import get_yaml_defaults
from cassey.config.llm_factory import validate_llm_config
from cassey.logging import configure_logging
from cassey.tools.registry import get_all_tools
from cassey.storage.checkpoint import get_async_checkpointer
from cassey.storage.user_registry import UserRegistry
from cassey.channels.telegram import TelegramChannel
from cassey.channels.http import HttpChannel
from cassey.agent.langchain_agent import create_langchain_agent
from cassey.agent.prompts import get_system_prompt
from cassey.scheduler import start_scheduler, stop_scheduler, register_notification_handler


def config_verify() -> int:
    """Verify configuration loading and print status.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    print("Cassey Configuration Verification")
    print("=" * 40)

    errors = []
    warnings = []

    # 1. Check config.yaml
    try:
        defaults = get_yaml_defaults()
        print(f"✓ config.yaml loaded ({len(defaults)} keys)")
    except Exception as e:
        errors.append(f"config.yaml: {e}")
        print(f"✗ config.yaml: {e}")

    # 2. Check storage paths
    try:
        for path_name, path_value in [
            ("SHARED_ROOT", settings.SHARED_ROOT),
            ("GROUPS_ROOT", settings.GROUPS_ROOT),
            ("USERS_ROOT", settings.USERS_ROOT),
        ]:
            path = Path(path_value)
            if path.exists() or path.parent.exists():
                print(f"✓ {path_name}: {path_value}")
            else:
                print(f"  {path_name}: {path_value} (will be created)")
    except Exception as e:
        errors.append(f"Storage paths: {e}")
        print(f"✗ Storage paths: {e}")

    # 3. Check LLM configuration
    try:
        validate_llm_config()
        print(f"✓ LLM provider: {settings.DEFAULT_LLM_PROVIDER}")
    except ValueError as e:
        errors.append(f"LLM config: {e}")
        print(f"✗ LLM config: {e}")

    # 4. Check required secrets
    required_secrets = {
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "ZHIPUAI_API_KEY": settings.ZHIPUAI_API_KEY,
        "OLLAMA_CLOUD_API_KEY": settings.OLLAMA_CLOUD_API_KEY,
    }

    has_llm_key = False
    for key_name, key_value in required_secrets.items():
        if key_value and key_value not in ["sk-ant-xxx", "sk-xxx", "your-zhipu-key", "your-ollama-cloud-api-key"]:
            has_llm_key = True
            break

    if has_llm_key:
        print(f"✓ LLM API key configured")
    else:
        warnings.append("No LLM API key found")
        print(f"⚠ No LLM API key found (set ANTHROPIC_API_KEY or OPENAI_API_KEY)")

    # 5. Check database configuration
    try:
        print(f"✓ PostgreSQL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    except Exception as e:
        errors.append(f"PostgreSQL config: {e}")
        print(f"✗ PostgreSQL config: {e}")

    # 6. Check checkpoint storage
    print(f"✓ Checkpoint storage: {settings.CHECKPOINT_STORAGE}")

    # Summary
    print("=" * 40)
    if errors:
        print(f"\n❌ Verification failed with {len(errors)} error(s)")
        for error in errors:
            print(f"  - {error}")
        return 1

    if warnings:
        print(f"\n⚠️  Verification passed with {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("\n✅ All checks passed!")

    return 0


def get_channels():
    """Get configured channels based on environment."""
    channels_str = os.getenv("CASSEY_CHANNELS", "telegram").lower()
    return [c.strip() for c in channels_str.split(",")]


async def main() -> None:
    """Start the Cassey bot."""
    configure_logging()

    # Validate LLM configuration on startup
    try:
        validate_llm_config()
    except ValueError as e:
        print(f"\n{e}\n")
        print("Please configure your LLM settings in .env file.")
        sys.exit(1)

    # Create LLM model
    model = create_model()
    print(f" Using LLM provider: {settings.DEFAULT_LLM_PROVIDER}")

    # Load tools
    tools = await get_all_tools()
    print(f" Loaded {len(tools)} tools")

    # Create checkpointer
    checkpointer = await get_async_checkpointer()
    print(f" Checkpointer: {settings.CHECKPOINT_STORAGE}")

    print(" Agent runtime: langchain")

    agent_cache: dict[str, Any] = {}

    def build_agent(channel_name: str) -> Any:
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
            agent = build_agent("telegram")
            channel = TelegramChannel(agent=agent)
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
            agent = build_agent("http")
            channel = HttpChannel(
                agent=agent,
                host=os.getenv("HTTP_HOST", "0.0.0.0"),
                port=int(os.getenv("HTTP_PORT", "8000")),
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
    """Synchronous entry point for console script.

    Handles CLI commands:
    - cassey config verify - Verify configuration
    - cassey (no args) - Start the bot
    """
    # Check for CLI commands
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "config":
            if len(sys.argv) > 2 and sys.argv[2].lower() == "verify":
                sys.exit(config_verify())
            else:
                print("Available commands:")
                print("  cassey config verify  - Verify configuration")
                sys.exit(1)

    # Default: start the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run_main()
