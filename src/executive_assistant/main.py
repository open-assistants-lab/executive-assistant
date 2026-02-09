"""Main entry point for running Executive Assistant bot."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

# Load environment variables from .env file before importing other modules
from dotenv import load_dotenv
load_dotenv("docker/.env", override=False)

from executive_assistant.config import create_model, settings
from executive_assistant.config.loader import get_yaml_defaults
from executive_assistant.config.llm_factory import validate_llm_config
from executive_assistant.logging import configure_logging, format_log_context
from executive_assistant.tools.registry import get_all_tools
from executive_assistant.storage.checkpoint import get_async_checkpointer
from executive_assistant.storage.user_registry import UserRegistry
from executive_assistant.storage.user_allowlist import allowlist_writable
from executive_assistant.channels.telegram import TelegramChannel
from executive_assistant.channels.http import HttpChannel
from executive_assistant.agent.langchain_agent import create_langchain_agent
from executive_assistant.skills import SkillsBuilder
from executive_assistant.agent.prompts import get_default_prompt, get_channel_prompt, load_admin_prompt
from executive_assistant.scheduler import start_scheduler, stop_scheduler, register_notification_handler
from executive_assistant.skills import load_and_register_skills, get_skills_registry

logger = logging.getLogger(__name__)


def config_verify() -> int:
    """Verify configuration loading and print status.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    print("Executive Assistant Configuration Verification")
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
    """Get configured channels based on config.yaml or environment."""
    from executive_assistant.config import settings
    channels_str = settings.EXECUTIVE_ASSISTANT_CHANNELS.lower()
    return [c.strip() for c in channels_str.split(",")]


async def main() -> None:
    """Start the Executive Assistant bot."""
    configure_logging()

    if not allowlist_writable():
        logger.warning(f'{format_log_context("system", component="startup")} allowlist_not_writable path="{settings.ADMINS_ROOT}/user_allowlist.json"')

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

    # Create skills registry
    registry = get_skills_registry()

    # Load admin skills FIRST (so they appear before system skills in prompt)
    admin_skills_dir = settings.ADMINS_ROOT / "skills"
    has_admin_skills = False
    if admin_skills_dir.exists():
        from executive_assistant.skills.loader import load_skills_from_directory
        admin_result = load_skills_from_directory(admin_skills_dir)
        # Register all admin skills as startup
        for skill in admin_result.startup + admin_result.on_demand:
            registry.register(skill)
        admin_total = len(admin_result.startup) + len(admin_result.on_demand)
        if admin_total > 0:
            has_admin_skills = True
            print(f" Loaded {admin_total} admin skills")

    # Load system skills from content directory (loaded AFTER admin skills)
    # Skip onboarding skill if admin skills are present (specialized mode)
    from executive_assistant.skills.loader import load_skills_from_directory
    skills_dir = Path(__file__).parent / "skills" / "content"
    system_result = load_skills_from_directory(skills_dir)

    # Filter out onboarding if admin skills present (specialized mode)
    startup_skills_to_load = system_result.startup
    if has_admin_skills:
        startup_skills_to_load = [
            s for s in system_result.startup
            if "onboarding" not in s.name.lower()
        ]
        if len(startup_skills_to_load) < len(system_result.startup):
            print(f" Skipping onboarding (admin skills present - specialized mode)")

    # Register system skills
    for skill in startup_skills_to_load:
        registry.register(skill)
    for skill in system_result.on_demand:
        if "on_demand" not in skill.tags:
            skill.tags.append("on_demand")
        registry.register(skill)

    print(f" Loaded {len(startup_skills_to_load)} startup skills, {len(system_result.on_demand)} on-demand skills")

    # Load tools (includes load_skill tool)
    tools = await get_all_tools()
    print(f" Loaded {len(tools)} tools")

    # Create skills builder (adds skill descriptions to system prompt)
    skills_builder = SkillsBuilder(registry)

    # Create checkpointer
    checkpointer = await get_async_checkpointer()
    print(f" Checkpointer: {settings.CHECKPOINT_STORAGE}")

    print(" Agent runtime: langchain")

    agent_cache: dict[str, Any] = {}

    def build_agent(channel_name: str) -> Any:
        cache_key = f"langchain:{channel_name}"
        if cache_key not in agent_cache:
            # Build prompt: admin -> system -> admin skills -> system skills -> channel
            base_prompt = get_default_prompt()
            admin_prompt = load_admin_prompt()
            if admin_prompt:
                base_prompt = f"{admin_prompt}\n\n{base_prompt}"
            # Skills are loaded from registry by the builder (includes startup + admin skills)
            system_prompt = skills_builder.build_prompt(base_prompt)
            channel_prompt = get_channel_prompt(channel_name)
            if channel_prompt:
                system_prompt = f"{system_prompt}\n\n{channel_prompt}"
            # Create agent with enhanced prompt
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
    logger.info(f'{format_log_context("system", component="startup")} scheduler_starting')
    await start_scheduler()
    logger.info(f'{format_log_context("system", component="startup")} scheduler_started')
    print(" Reminder scheduler started", flush=True)

    # Determine which channels to run
    enabled_channels = get_channels()
    logger.info(f'{format_log_context("system", component="startup")} channels_enabled={enabled_channels}')
    active_channels = []

    for channel_name in enabled_channels:
        logger.info(f'{format_log_context("system", component="startup")} channel_create name={channel_name}')
        if channel_name == "telegram":
            logger.info(f'{format_log_context("system", component="startup")} telegram_agent_build')
            agent = build_agent("telegram")
            logger.info(f'{format_log_context("system", component="startup")} telegram_channel_create')
            channel = TelegramChannel(agent=agent)
            logger.info(f'{format_log_context("system", component="startup")} registry_set')
            channel.registry = registry

            # Register notification handler for reminders
            bot_name_cache = {"name": None}
            async def telegram_notification_handler(thread_id, message, channel_ref=channel):
                """Send reminder notification via Telegram."""
                # Extract chat_id from thread_id (format: telegram:chat_id)
                if thread_id.startswith("telegram:"):
                    chat_id = thread_id.split(":", 1)[1]
                    bot_name = bot_name_cache["name"]
                    if not bot_name and channel_ref.application:
                        try:
                            me = await channel_ref.application.bot.get_me()
                            bot_name = me.username or me.first_name or "unknown"
                            bot_name_cache["name"] = bot_name
                        except Exception as e:
                            logger.warning(
                                f'{format_log_context("system", component="telegram", channel="telegram")} reminder_bot_lookup_failed error="{e}"'
                            )
                            bot_name = "unknown"
                    logger.info(
                        f'{format_log_context("system", component="telegram", channel="telegram")} reminder_send bot="{bot_name}" chat_id={chat_id}'
                    )
                    await channel_ref.send_message(chat_id, f"🔔 Reminder: {message}")

            register_notification_handler("telegram", telegram_notification_handler)

            active_channels.append(channel)
            print(" Telegram channel created", flush=True)
        elif channel_name == "http":
            logger.info(f'{format_log_context("system", component="startup")} http_channel_create')
            agent = build_agent("http")
            channel = HttpChannel(
                agent=agent,
                host=os.getenv("HTTP_HOST", "0.0.0.0"),
                port=int(os.getenv("HTTP_PORT", "8000")),
            )
            channel.registry = registry

            # Register notification handler for reminders
            async def http_notification_handler(thread_id, message):
                """Persist HTTP notification into conversation history."""
                try:
                    from langchain_core.messages import AIMessage

                    # thread_id is expected to be "http:{conversation_id}"
                    conversation_id = thread_id.split(":", 1)[1] if ":" in thread_id else thread_id
                    await registry.log_message(
                        conversation_id=thread_id,
                        channel="http",
                        message=AIMessage(content=f"🔔 {message}"),
                        metadata={
                            "notification": True,
                            "notification_channel": "http",
                            "http_conversation_id": conversation_id,
                        },
                    )
                    logger.info(
                        f'{format_log_context("system", component="http", channel="http", user=thread_id, conversation=conversation_id)} notification_persisted'
                    )
                except Exception as e:
                    logger.warning(
                        f'{format_log_context("system", component="http", channel="http", user=thread_id)} notification_persist_failed error="{e}"'
                    )

            register_notification_handler("http", http_notification_handler)

            active_channels.append(channel)
            print(f" HTTP channel created (port {channel.port})")
        else:
            print(f" Unknown channel: {channel_name}")

    logger.info(f'{format_log_context("system", component="startup")} channel_loop_complete active={len(active_channels)}')
    if not active_channels:
        print(" Error: No valid channels configured")
        await stop_scheduler()
        sys.exit(1)

    # Setup graceful shutdown
    logger.info(f'{format_log_context("system", component="startup")} shutdown_handlers_setup')
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\nShutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start all channels
    print("\nExecutive Assistant is starting...", flush=True)
    for i, channel in enumerate(active_channels):
        logger.info(f'{format_log_context("system", component="startup")} channel_start index={i+1} total={len(active_channels)}')
        await channel.start()
        logger.info(f'{format_log_context("system", component="startup")} channel_started index={i+1}')

    logger.info(f'{format_log_context("system", component="startup")} channels_ready')
    
    # Import cleanup module
    from executive_assistant.storage.cleanup import cleanup_all
    
    try:
        print(f" Bot is running. Channels: {', '.join(enabled_channels)}. Press Ctrl+C to stop.", flush=True)
        await shutdown_event.wait()
    finally:
        print("\nShutting down...")
        logger.info(f'{format_log_context("system", component="shutdown")} stopping_channels')
        for channel in active_channels:
            await channel.stop()
        logger.info(f'{format_log_context("system", component="shutdown")} stopping_scheduler')
        await stop_scheduler()
        logger.info(f'{format_log_context("system", component="shutdown")} cleaning_up_resources')
        cleanup_all()
        logger.info(f'{format_log_context("system", component="shutdown")} complete')
        print(" Bot stopped")


def run_main() -> None:
    """Synchronous entry point for console script.

    Handles CLI commands:
    - executive_assistant config verify - Verify configuration
    - executive_assistant (no args) - Start the bot
    """
    # Check for CLI commands
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "config":
            if len(sys.argv) > 2 and sys.argv[2].lower() == "verify":
                sys.exit(config_verify())
            else:
                print("Available commands:")
                print("  executive_assistant config verify  - Verify configuration")
                sys.exit(1)

    # Default: start the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run_main()
