"""Administrative commands for the Executive Assistant.

This module provides commands that work across all interfaces (CLI, HTTP, Telegram):
- /help - Show available commands
- /model - Get or change the current model
- /clear - Clear conversation history
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from src.config.settings import get_settings, parse_model_string
from src.llm import list_providers
from src.utils import create_thread_id
from src.commands.model_registry import (
    clear_current_model,
    get_current_model,
    get_effective_model,
    set_current_model,
)


def get_help_text() -> str:
    """Get help text showing available commands.

    Returns formatted help text for all interfaces.
    """
    settings = get_settings()
    agent_name = settings.agent_name

    return f"""{agent_name} - Executive Assistant

Available Commands:

/help
    Show this help message

/model [provider/model]
    Show or change the current LLM model
    Examples:
      /model                    → Show current model
      /model openai/gpt-4o      → Change model
      /model ollama/qwen3-coder  → Change model

/clear
    Clear conversation history and start a new thread

Built-in Tools:
    get_current_time    - Get current time in any timezone
    web_search          - Search the web
    web_scrape          - Scrape content from a URL
    web_crawl           - Crawl a website
    web_map             - Map a website (discover URLs)
    memory_search       - Search memory store
    memory_timeline     - Get timeline context
    memory_get          - Get full memory details
    memory_save         - Save information to memory
    write_todos         - Create/manage todo list

Available Providers:
{list_providers_text()}
"""


def list_providers_text() -> str:
    """Format list of available providers for help text."""
    providers = list_providers()
    return "\n".join([f"  - {p}" for p in sorted(providers)])


def handle_model_command(
    model_string: str | None,
    user_id: str,
    get_current_model: Callable[[str], tuple[str, str] | None],
    set_model: Callable[[str, str, str], None],
) -> str:
    """Handle /model command to get or change the model.

    Args:
        model_string: Model string (e.g., "openai/gpt-4o") or None to show current
        user_id: User ID for model storage
        get_current_model: Function to get current model for user
        set_model: Function to set model for user

    Returns:
        Response message
    """
    if not model_string:
        # Show current model
        current = get_current_model(user_id)
        if current:
            provider, model = current
            return f"Current model: {provider}/{model}\n\nUsage: /model <provider/model>\nExample: /model openai/gpt-4o"
        else:
            return "No model set. Usage: /model <provider/model>\nExample: /model openai/gpt-4o"

    # Change model
    try:
        provider, model = parse_model_string(model_string)
        set_model(user_id, provider, model)
        return f"Model changed to: {provider}/{model}"
    except ValueError as e:
        return f"Error: {e}\n\nUsage: /model <provider/model>\nExample: /model openai/gpt-4o"


def handle_clear_command(user_id: str, thread_id: str) -> str:
    """Handle /clear command to clear conversation history.

    Args:
        user_id: User ID
        thread_id: New thread ID for the fresh session

    Returns:
        Response message
    """
    new_thread_id = thread_id or create_thread_id(user_id=user_id, channel="session", reason="clear")
    return f"Conversation history cleared.\nNew thread ID: {new_thread_id}"


__all__ = [
    "clear_current_model",
    "get_current_model",
    "get_effective_model",
    "get_help_text",
    "handle_clear_command",
    "handle_model_command",
    "set_current_model",
]
