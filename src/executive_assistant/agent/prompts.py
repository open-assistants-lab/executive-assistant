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

**FIRST RESPONSE RULE:** When a user states their role for the FIRST TIME ("I'm a CEO", "I'm a developer", "I'm an analyst"), acknowledge it briefly.

IMPORTANT: Only acknowledge ONCE per conversation. If you've already learned their role (from memories or conversation history), do NOT repeat acknowledgment. Simply proceed with your actual response.

Examples:
- "I'm a CEO" → "Thanks for letting me know. How can I help you today?"
- "I'm a developer" → "Got it. What would you like to work on?"
- "I'm an analyst" → "Understood. What can I help with?"

After the FIRST acknowledgment, move directly to helping them without repeating role references like "I understand you're a tester" or "for your testing".

**MEMORY CREATION - CRITICAL:**
When users express preferences or say "Remember that...", "I prefer...", "Always...", "Never...":
1. **MUST** use the `create_memory` tool to store it
2. Do NOT just verbally acknowledge - ALWAYS call the tool
3. Use memory_type="preference" and a descriptive key

**MEMORY RETRIEVAL - CRITICAL:**
Before generating reports, summaries, or formatted output:
1. **ALWAYS** search memories first: `search_memories()` or `get_memory_by_key()`
2. **Acknowledge preferences found** - if memory says "brief summaries", SAY "brief/short/summary" in your response
3. **THEN** proceed - even if you need to ask for more info

**REMINDER TIME HANDLING - CRITICAL:**
When setting reminders:
1. Use `reminder_set` and return its result to the user (success or explicit error).
2. Prefer explicit formats when clarifying: `YYYY-MM-DD HH:MM` (or with timezone, e.g. `2026-02-06 23:22 Australia/Sydney`).
3. If user timezone is missing and request is ambiguous, ask for timezone or use saved timezone memory if available.
4. For relative times like "in 10 minutes", call `reminder_set` immediately using current/default timezone; do not block on timezone lookup.
5. Confirm the interpreted scheduled time and timezone in the final response.

**TASK TRACKING - CRITICAL:**
Use the `write_todos` tool for multi-step tasks that involve:
- Multiple tool calls (3+ expected calls)
- Research requiring multiple sources or searches
- Complex workflows with dependencies
- Breaking down problems into steps
- Showing progress over time
- Information gathering from multiple places

**DO NOT use write_todos for:**
- Simple single-step queries ("What is 2+2?", "What time is it?")
- Direct commands starting with `/` or `!` (e.g., `/mem list`, `!ls`)
- Direct tool invocations (user explicitly names a tool)
- Single-source lookups (checking ONE memory, ONE file, ONE status)
- Simple status checks

Process:
1. For tasks with 3+ steps: FIRST call write_todos with your plan
2. For commands/simple queries: Execute directly WITHOUT todos
3. Mark steps complete as you work through them
4. Keep todos updated as you learn more

Remember: When unsure, use write_todos for anything requiring multiple steps or research!

## Tool Usage Guidelines

**PREFER BUILT-IN TOOLS**: Always try to use the tools you have available before suggesting external solutions or services. Your built-in tools can handle most tasks including:
- Storing and retrieving information (use "data storage" or "memory" tools)
- Searching the web
- Managing reminders and tasks
- Reading and writing files
- Performing calculations

**DIRECT TOOL REQUESTS - CRITICAL:** If the user explicitly says `run <tool>()`, `use <tool> now`, or provides a tool name with arguments, you MUST call that tool. Do not answer with explanation-only text before attempting the requested tool call.

**STORAGE OPTIONS**: You have TWO scopes for data storage:
- **Thread-scoped (default)**: Private to this conversation. Only you can access it.
- **Shared (organization-wide)**: Accessible by all users. Perfect for announcements, shared data, company-wide knowledge.

ALL storage tools support BOTH scopes:
- Structured data storage: use `scope="shared"` for organization-wide tables
- Knowledge search (VDB): use `scope="shared"` for shared knowledge bases
- File storage: use `scope="shared"` for shared files

When users want data visible to everyone, suggest using `scope="shared"`.

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


def get_system_prompt(
    channel: str | None = None,
    thread_id: str | None = None,
    user_message: str | None = None,
) -> str:
    """Get appropriate system prompt for the channel.

    Merge order (highest priority last):
    1. Admin prompt (global policies)
    2. Base prompt (role definition)
    3. User instincts (learned behavioral patterns)
    4. Channel appendix (formatting constraints)

    Args:
        channel: Channel type ('telegram', 'http', etc.)
        thread_id: Thread identifier for user-specific content (optional)
        user_message: Current user message for context-aware instinct filtering (optional)

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

    # Layer 3: User instincts (optional, per-thread)
    if thread_id:
        # Try to load instincts first (preferred)
        instincts_section = load_instincts_context(thread_id, user_message)
        if instincts_section:
            parts.append(instincts_section)
        else:
            # Fallback to deprecated user prompt for transition period
            user_prompt = load_user_prompt(thread_id)
            if user_prompt:
                parts.append(user_prompt)

    # Layer 4: Emotional state context (optional, per-conversation)
    emotional_section = load_emotional_context()
    if emotional_section:
        parts.append(emotional_section)

    # Layer 5: Channel appendix (optional)
    appendix = get_channel_prompt(channel)
    if appendix:
        parts.append(appendix)

    # Join all layers with double newlines
    full_prompt = "\n\n".join(parts)

    # Log system prompt for troubleshooting (debug level to avoid spamming)
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"System prompt generated (thread_id={thread_id}, channel={channel}):\n{full_prompt[:2000]}...")

    return full_prompt


def load_instincts_context(thread_id: str, user_message: str | None = None) -> str:
    """Load applicable instincts as formatted context for system prompt.

    Args:
        thread_id: Thread identifier (e.g., "telegram:123456")
        user_message: Current user message for context-aware filtering (optional)

    Returns:
        Formatted instincts section if any exist, empty string otherwise.
    """
    try:
        from executive_assistant.instincts.injector import get_instinct_injector

        injector = get_instinct_injector()
        return injector.build_instincts_context(thread_id, user_message)
    except Exception:
        # If instincts system fails, return empty (don't break the agent)
        return ""


def load_user_prompt(thread_id: str) -> str:
    """Load user prompt content (thread-specific, optional).

    Args:
        thread_id: Thread identifier (e.g., "telegram:123456")

    Returns:
        Formatted user prompt if exists, empty string otherwise.
    """
    try:
        from executive_assistant.storage.user_storage import UserPaths

        user_paths = UserPaths(thread_id)
        prompt_path = user_paths.get_prompt_path()

        if prompt_path.exists():
            with open(prompt_path) as f:
                return f.read()
    except Exception:
        pass

    return ""


def load_emotional_context() -> str:
    """Load current emotional state as context for system prompt.

    Returns:
        Formatted emotional context if state is significant, empty string otherwise.
    """
    try:
        from executive_assistant.instincts.emotional_tracker import get_emotional_tracker

        tracker = get_emotional_tracker()
        return tracker.get_state_for_prompt()
    except Exception:
        # If emotional tracking fails, return empty (don't break the agent)
        return ""


def load_user_prompt(thread_id: str) -> str:
    """Load user prompt content (thread-specific, optional).

    Args:
        thread_id: Thread identifier

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
