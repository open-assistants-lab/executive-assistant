"""System prompts for the agent."""

from executive_assistant.config import settings

TELEGRAM_APPENDIX = """Telegram Formatting:
- Use short bullets or numbered lists
- Avoid markdown tables
- Keep responses concise
"""

HTTP_APPENDIX = """HTTP Formatting:
- Use standard markdown
- Use headings and lists for longer responses
"""


def get_channel_prompt(channel: str | None = None) -> str:
    """Get channel-specific prompt appendix only."""
    if channel == "telegram":
        return TELEGRAM_APPENDIX
    if channel == "http":
        return HTTP_APPENDIX
    return ""


def _get_telegram_prompt() -> str:
    """Get Telegram-specific system prompt with agent name."""
    return f"{get_default_prompt()}\n\n{TELEGRAM_APPENDIX}"


def _get_http_prompt() -> str:
    """Get HTTP-specific system prompt with agent name."""
    return f"{get_default_prompt()}\n\n{HTTP_APPENDIX}"


def get_default_prompt() -> str:
    """Get the default system prompt with agent name."""
    return f"""You are {settings.AGENT_NAME}, a personal AI assistant.

Help with tasks, questions, and organizing information. Be clear and practical.
If you can't do something with available tools, say so.
"""


def get_system_prompt(channel: str | None = None) -> str:
    """Get appropriate system prompt for the channel.

    Args:
        channel: Channel type ('telegram', 'http', etc.)

    Returns:
        System prompt with channel-specific constraints and formatting.
    """
    base = get_default_prompt()
    appendix = get_channel_prompt(channel)
    if appendix:
        return f"{base}\n\n{appendix}"
    return base


def load_admin_prompt() -> str:
    """Load admin prompt content (global, optional)."""
    prompt_path = settings.ADMINS_ROOT / "prompts" / "prompt.md"
    if not prompt_path.exists():
        return ""
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
