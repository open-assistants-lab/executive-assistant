"""Telegram bot integration for Executive Assistant.

This package provides Telegram bot functionality using lazy imports to avoid
circular import warnings when running the bot directly.
"""

__all__ = [
    "TelegramBot",
    "create_bot",
    "get_bot",
    "run_bot",
    "run_bot_sync",
    "MessageFormatter",
    "MessageUpdater",
]


def __getattr__(name: str):
    """Lazy import to avoid circular import warning.

    This function is called when an attribute is accessed but not found
    in the module's __dict__. It performs lazy imports only when needed.
    """
    if name == "TelegramBot":
        from src.telegram.bot import TelegramBot
        return TelegramBot
    elif name == "create_bot":
        from src.telegram.bot import create_bot
        return create_bot
    elif name == "get_bot":
        from src.telegram.bot import get_bot
        return get_bot
    elif name == "run_bot":
        from src.telegram.bot import run_bot
        return run_bot
    elif name == "run_bot_sync":
        from src.telegram.bot import run_bot_sync
        return run_bot_sync
    elif name == "MessageFormatter":
        from src.telegram.formatters import MessageFormatter
        return MessageFormatter
    elif name == "MessageUpdater":
        from src.telegram.formatters import MessageUpdater
        return MessageUpdater

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
