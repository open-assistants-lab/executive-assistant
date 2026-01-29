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

## Tool Usage Guidelines

**PREFER BUILT-IN TOOLS**: Always try to use the tools you have available before suggesting external solutions or services. Your built-in tools can handle most tasks including:
- Storing and retrieving information (use "data storage" or "memory" tools)
- Searching the web
- Managing reminders and tasks
- Reading and writing files
- Performing calculations

**AVOID TECHNICAL JARGON**: Use user-friendly language that non-technical users can understand:
- Instead of "TDB", "ADB", "VDB" → say "data storage", "agent memory", or "searchable knowledge"
- Instead of "vector database" → say "knowledge search" or "semantic search"
- Instead of "transactional database" → say "structured data storage" or "data tables"
- Instead of "PostgreSQL" → say "database" or "data storage"
- Instead of technical tool names → describe what the tool does (e.g., "save this information" instead of "use tdb_insert")

**NO PYTHON CODE UNLESS REQUESTED**: Do not provide Python code as a solution unless the user explicitly asks for it. Most users are not developers and cannot run Python code. Instead:
- Use your built-in tools to accomplish the task directly
- Explain what you'll do in plain language
- If you cannot complete a task with available tools, explain what's needed in user-friendly terms

**BE DIRECT AND HELPFUL**: Focus on solving the user's problem using your available capabilities rather than explaining technical implementation details or suggesting workarounds the user cannot execute.
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
