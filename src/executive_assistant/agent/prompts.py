"""System prompts for the agent."""

import logging

from executive_assistant.config import settings

logger = logging.getLogger(__name__)

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


def _estimate_tokens(text: str) -> int:
    """Approximate token count without model-specific tokenizer dependencies."""
    if not text:
        return 0
    # Rough heuristic for GPT-style tokenization in English prose.
    return max(1, (len(text) + 3) // 4)


def _truncate_to_token_budget(text: str, max_tokens: int, layer_name: str) -> str:
    """Truncate text to approximate token budget, preserving top-priority content."""
    if not text or max_tokens <= 0:
        return ""

    if _estimate_tokens(text) <= max_tokens:
        return text

    target_chars = max_tokens * 4
    truncated = text[:target_chars].rstrip()
    if "\n" in truncated:
        truncated = truncated.rsplit("\n", 1)[0].rstrip()
    if not truncated:
        return ""
    return f"{truncated}\n\n[...{layer_name} truncated for prompt budget]"


def _apply_layer_cap(text: str, max_tokens: int, layer_name: str) -> str:
    """Apply per-layer cap with lightweight telemetry."""
    if not text:
        return ""
    before = _estimate_tokens(text)
    if before <= max_tokens:
        return text
    after = _truncate_to_token_budget(text, max_tokens, layer_name)
    logger.debug(
        "Prompt layer capped: layer=%s before=%s after=%s",
        layer_name,
        before,
        _estimate_tokens(after),
    )
    return after


def _apply_total_budget(layers: dict[str, str], max_total_tokens: int) -> dict[str, str]:
    """Apply deterministic truncation order to keep total prompt under budget."""
    if max_total_tokens <= 0:
        return layers

    total = sum(_estimate_tokens(text) for text in layers.values())
    if total <= max_total_tokens:
        return layers

    # Lowest-priority guidance trimmed first.
    trim_order = [
        ("emotional", 0),
        ("instincts", 40),
        ("user_prompt", 60),
        ("skills", 60),
        ("admin", 120),
    ]

    updated = dict(layers)
    excess = total - max_total_tokens
    for layer_name, min_keep in trim_order:
        text = updated.get(layer_name, "")
        if not text:
            continue
        current_tokens = _estimate_tokens(text)
        removable = max(current_tokens - min_keep, 0)
        if removable <= 0:
            continue

        shrink = min(removable, excess)
        target = current_tokens - shrink
        updated[layer_name] = (
            _truncate_to_token_budget(text, target, layer_name) if target > 0 else ""
        )
        excess -= shrink
        if excess <= 0:
            break

    return updated


def _log_prompt_telemetry(
    channel: str | None,
    thread_id: str | None,
    layers: dict[str, str],
) -> None:
    """Emit per-layer prompt token telemetry for budget tracking."""
    if not settings.PROMPT_TELEMETRY_ENABLED:
        return

    layer_tokens = {
        name: _estimate_tokens(text)
        for name, text in layers.items()
        if text
    }
    total_tokens = sum(layer_tokens.values())
    token_summary = ", ".join(f"{name}={count}" for name, count in layer_tokens.items())
    log_msg = (
        "System prompt telemetry: total_tokens=%s channel=%s thread_id=%s layers=[%s]"
    )
    args = (total_tokens, channel or "-", thread_id or "-", token_summary)

    if total_tokens >= settings.PROMPT_ERROR_TOKENS:
        logger.error(log_msg, *args)
    elif total_tokens >= settings.PROMPT_WARN_TOKENS:
        logger.warning(log_msg, *args)
    else:
        logger.debug(log_msg, *args)


def load_skills_context() -> str:
    """Load compact skill index for the system prompt."""
    if not settings.PROMPT_INCLUDE_SKILLS_INDEX:
        return ""

    try:
        from executive_assistant.skills.builder import SkillsBuilder
        from executive_assistant.skills.registry import get_skills_registry

        registry = get_skills_registry()
        if not registry.list_all():
            return ""

        builder = SkillsBuilder(registry)
        return builder.build_skills_section(include_startup_content=False)
    except Exception as exc:
        logger.debug("Failed to load skills context: %s", exc)
        return ""


def _get_telegram_prompt() -> str:
    """Get Telegram-specific system prompt with agent name."""
    return get_system_prompt(channel="telegram")


def _get_http_prompt() -> str:
    """Get HTTP-specific system prompt with agent name."""
    return get_system_prompt(channel="http")


def get_default_prompt() -> str:
    """Get the default system prompt with agent name."""
    return f"""You are {settings.AGENT_NAME}, a personal AI assistant.

Help with tasks, questions, and organizing information. Be clear and practical.
If you can't do something with available tools, say so.

Core execution rules:
- First role mention in a conversation: acknowledge briefly once, then continue normally without repeating role references.
- Memory capture: when user says "remember", "I prefer", "always", "never", call `create_memory` (usually `memory_type="preference"`).
- Memory retrieval: before reports/summaries/formatted outputs, search memories first and reflect found preferences in response style.
- Reminder handling: use `reminder_set`; for relative times execute immediately; clarify timezone when ambiguous; confirm interpreted datetime/timezone.
- Task tracking: use `write_todos` for multi-step work (typically 3+ tool calls, multi-source research, or dependent workflows). Skip it for simple queries, direct commands (`/`, `!`), explicit tool invocations, or single-source checks.

Tool and response rules:
- Prefer built-in tools over external suggestions.
- If user explicitly requests `run <tool>()` / `use <tool>` / tool+args, call the requested tool first.
- Be direct, practical, and outcome-focused.

Storage and language rules:
- Storage scopes: `context` (thread-private) and `shared` (organization-wide). Suggest `shared` for org-visible data.
- Avoid technical jargon in user-facing text; use plain language (e.g., "data storage", "knowledge search", "memory").
- Do not provide Python code unless user explicitly asks for code.
"""


def get_system_prompt(
    channel: str | None = None,
    thread_id: str | None = None,
    user_message: str | None = None,
    include_skills: bool | None = None,
) -> str:
    """Build canonical system prompt used by all runtime paths."""
    include_skills_layer = (
        settings.PROMPT_INCLUDE_SKILLS_INDEX if include_skills is None else include_skills
    )

    admin_prompt = _apply_layer_cap(
        load_admin_prompt(),
        settings.PROMPT_LAYER_CAP_ADMIN_TOKENS,
        "admin",
    )
    base_prompt = get_default_prompt()
    skills_prompt = ""
    if include_skills_layer:
        skills_prompt = _apply_layer_cap(
            load_skills_context(),
            settings.PROMPT_LAYER_CAP_SKILLS_TOKENS,
            "skills",
        )

    instincts_prompt = ""
    user_prompt = ""
    emotional_prompt = ""

    if thread_id:
        instincts_prompt = _apply_layer_cap(
            load_instincts_context(thread_id, user_message),
            settings.PROMPT_LAYER_CAP_INSTINCT_TOKENS,
            "instincts",
        )
        if not instincts_prompt:
            user_prompt = _apply_layer_cap(
                load_user_prompt(thread_id),
                settings.PROMPT_LAYER_CAP_USER_PROMPT_TOKENS,
                "user_prompt",
            )
        emotional_prompt = _apply_layer_cap(
            load_emotional_context(thread_id),
            settings.PROMPT_LAYER_CAP_EMOTIONAL_TOKENS,
            "emotional",
        )

    channel_prompt = get_channel_prompt(channel)

    layers = {
        "admin": admin_prompt,
        "base": base_prompt,
        "skills": skills_prompt,
        "instincts": instincts_prompt,
        "user_prompt": user_prompt,
        "emotional": emotional_prompt,
        "channel": channel_prompt,
    }
    layers = _apply_total_budget(layers, settings.PROMPT_MAX_SYSTEM_TOKENS)
    _log_prompt_telemetry(channel=channel, thread_id=thread_id, layers=layers)

    return "\n\n".join(text for text in layers.values() if text)


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
    """Load user prompt content (thread-specific, optional)."""
    from executive_assistant.storage.user_storage import UserPaths

    prompt_path = UserPaths.get_prompt_path(thread_id)
    if not prompt_path.exists():
        return ""

    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def load_emotional_context(thread_id: str | None = None) -> str:
    """Load current emotional state as context for system prompt.

    Returns:
        Formatted emotional context if state is significant, empty string otherwise.
    """
    try:
        from executive_assistant.instincts.emotional_tracker import get_emotional_tracker

        tracker = get_emotional_tracker(thread_id)
        return tracker.get_state_for_prompt()
    except Exception:
        # If emotional tracking fails, return empty (don't break the agent)
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
    from executive_assistant.storage.user_storage import UserPaths

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
    from executive_assistant.storage.user_storage import UserPaths

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
