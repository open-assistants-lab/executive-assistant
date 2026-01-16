"""Main entry point for the Cassey Telegram bot."""

import asyncio
import signal
import sys

from cassey.config import create_model, settings
from cassey.logging import configure_logging
from cassey.agent import create_graph
from cassey.channels import TelegramChannel
from cassey.storage import get_async_checkpointer, close_checkpointer
from cassey.tools import get_all_tools


def main_init() -> None:
    """
    Early initialization before async context.

    This configures logging and validates environment before
    entering the async context.
    """
    # Configure logging first (before any other imports that might log)
    log_file = getattr(settings, "LOG_FILE", None)
    log_level = getattr(settings, "LOG_LEVEL", "INFO")
    configure_logging(log_level=log_level, log_file=log_file)


async def main() -> None:
    """
    Start the Cassey Telegram bot.

    This function:
    1. Loads configuration from environment
    2. Creates the LLM model
    3. Loads all available tools
    4. Creates the ReAct agent graph
    5. Starts the Telegram channel
    """
    print("🤖 Cassey - Multi-channel AI Agent")
    print("=" * 40)

    # Validate configuration
    if not settings.TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Display configuration
    print(f"📊 Configuration:")
    print(f"  LLM Provider: {settings.DEFAULT_LLM_PROVIDER}")
    print(f"  Storage: {settings.CHECKPOINT_STORAGE}")
    print(f"  Files: {settings.FILES_ROOT}")
    print()

    # Create model
    print("🧠 Creating LLM model...")
    model = create_model()
    print(f"  ✓ Using {model.__class__.__name__}")

    # Load tools
    print("🔧 Loading tools...")
    tools = await get_all_tools()
    print(f"  ✓ Loaded {len(tools)} tools")
    for tool in tools:
        print(f"    - {tool.name}")

    # Create checkpointer
    print("💾 Setting up checkpoint storage...")
    checkpointer = await get_async_checkpointer()
    print(f"  ✓ Using {checkpointer.__class__.__name__}")

    # Create agent graph
    print("⚡ Creating ReAct agent graph...")
    agent = create_graph(model, tools, checkpointer)
    print("  ✓ Agent ready")

    # Create and start Telegram channel
    print("📱 Starting Telegram channel...")
    channel = TelegramChannel(agent=agent)

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig: int, frame) -> None:
        print("\n🛑 Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the channel
    await channel.start()
    print("✓ Bot is running! Press Ctrl+C to stop.")
    print()

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Graceful shutdown
    print("👋 Shutting down...")
    await channel.stop()
    await close_checkpointer()
    print("✓ Shutdown complete")


if __name__ == "__main__":
    try:
        # Early initialization (logging configuration)
        main_init()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
