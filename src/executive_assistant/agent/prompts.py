"""System prompts for the agent."""

import time
from pathlib import Path

from executive_assistant.config import settings
from executive_assistant.storage.user_storage import UserPaths

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


def get_system_prompt(channel: str | None = None, thread_id: str | None = None) -> str:
    """Get appropriate system prompt for the channel.

    Merge order (highest priority last):
    1. Admin prompt (global policies)
    2. Base prompt (role definition)
    3. User prompt (personal preferences) ← NEW
    4. Channel appendix (formatting constraints)

    Args:
        channel: Channel type ('telegram', 'http', etc.)
        thread_id: Thread identifier for user-specific prompt (optional)

    Returns:
        Complete system prompt with all layers merged.
    """
    parts = []

    # Layer 1: Admin prompt (optional, global)
    admin_prompt = load_admin_prompt()
    if admin_prompt:
        parts.append(admin_prompt)

    # Layer 2: Base prompt (required)
    parts.append(get_default_prompt())

    # Layer 3: User prompt (optional, per-thread) ← NEW
    if thread_id:
        user_prompt = load_user_prompt(thread_id)
        if user_prompt:
            parts.append(user_prompt)

    # Layer 4: Channel appendix (optional)
    appendix = get_channel_prompt(channel)
    if appendix:
        parts.append(appendix)

    # Join all layers with double newlines
    return "\n\n".join(parts)


def load_user_prompt(thread_id: str) -> str:
    """Load user prompt content (thread-specific, optional).

    Args:
        thread_id: Thread identifier (e.g., "telegram:123456")

    Returns:
        User prompt content if file exists, empty string otherwise.
    """
    prompt_path = UserPaths.get_prompt_path(thread_id)
    if not prompt_path.exists():
        return ""

    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def validate_user_prompt(prompt: str) -> tuple[bool, str]:
    """Validate user prompt for safety and size constraints.

    Args:
        prompt: User prompt content to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if prompt passes all checks
        - error_message: Error description if invalid, empty if valid
    """
    # Check size limit (2000 characters)
    max_length = 2000
    if len(prompt) > max_length:
        return False, f"Prompt too long ({len(prompt)} chars, max {max_length})"

    # Check for jailbreak/attempted override patterns
    forbidden_patterns = [
        "ignore previous instructions",
        "disregard all rules",
        "ignore all rules",
        "forget everything",
        "forget previous",
        "override safety",
        "bypass restrictions",
        "jailbreak",
        "act as if",
        "pretend you are",
        "you are now",
        "you must ignore",
    ]

    prompt_lower = prompt.lower()
    for pattern in forbidden_patterns:
        if pattern in prompt_lower:
            return False, f"Prompt contains forbidden pattern: '{pattern}'"

    # Check for path traversal attempts
    if "../" in prompt or "..\\" in prompt:
        return False, "Path traversal detected"

    # Check for null bytes
    if "\x00" in prompt:
        return False, "Null bytes detected"

    return True, ""


def save_user_prompt(thread_id: str, prompt: str) -> tuple[bool, str]:
    """Save user prompt to file after validation.

    Args:
        thread_id: Thread identifier
        prompt: User prompt content

    Returns:
        Tuple of (success, message)
    """
    # Validate prompt
    is_valid, error_msg = validate_user_prompt(prompt)
    if not is_valid:
        return False, error_msg

    # Ensure directory exists
    prompt_path = UserPaths.get_prompt_path(thread_id)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)

    # Write prompt
    try:
        prompt_path.write_text(prompt, encoding="utf-8")
        return True, "Prompt saved successfully"
    except Exception as e:
        return False, f"Failed to save prompt: {e}"


def delete_user_prompt(thread_id: str) -> tuple[bool, str]:
    """Delete user prompt file.

    Args:
        thread_id: Thread identifier

    Returns:
        Tuple of (success, message)
    """
    prompt_path = UserPaths.get_prompt_path(thread_id)

    if not prompt_path.exists():
        return False, "No prompt found"

    try:
        prompt_path.unlink()
        return True, "Prompt deleted"
    except Exception as e:
        return False, f"Failed to delete prompt: {e}"


def load_admin_prompt() -> str:
    """Load admin prompt content (global, optional)."""
    prompt_path = settings.ADMINS_ROOT / "prompts" / "prompt.md"
    if not prompt_path.exists():
        return ""
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
