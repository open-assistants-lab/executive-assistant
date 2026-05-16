"""SDK Agent Runner — creates and runs AgentLoop with proper wiring.

This is the bridge between the HTTP layer and the SDK AgentLoop.
It handles:
  - Creating LLM provider from config
  - Loading SDK-native tools (no more LangChain adapter)
  - Loading MCP tools via MCPToolBridge
  - Loading connector tools via ConnectKitBridge
  - Assembling SDK middlewares (memory, summarization)
  - Converting between WS protocol messages and StreamChunks
  - Thread-safe per-user agent instances

Skills are now discovery-based: available skill names are embedded
in the skills_list tool description dynamically, not in the system prompt.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.app_logging import get_logger
from src.config import get_settings
from src.sdk.loop import AgentLoop
from src.sdk.messages import Message, StreamChunk
from src.sdk.middleware_observation import ObservationMiddleware
from src.sdk.middleware_summarization import SummarizationMiddleware
from src.sdk.native_tools import get_native_tools
from src.sdk.providers.factory import create_model_from_config
from src.sdk.tools import ToolAnnotations, ToolDefinition

logger = get_logger()

_loop_cache: dict[str, AgentLoop] = {}
_loop_lock = asyncio.Lock()


def _seed_default_workspace() -> None:
    """Create the default Personal workspace if it doesn't exist."""
    try:
        from src.sdk.workspace_models import Workspace, load_workspace, save_workspace
        from src.storage.paths import DataPaths
        ws = load_workspace("personal")
        if ws is None:
            ws = Workspace.from_name("Personal")
            ws.description = "Default personal workspace"
            save_workspace(ws)
            dp = DataPaths(workspace_id="personal")
            dp.workspace_files_dir()
            dp.workspace_memory_dir()
            dp.workspace_subagents_dir()
    except Exception:
        pass


def _get_system_prompt(user_id: str, workspace_id: str | None = None) -> str:
    settings = get_settings()
    base_prompt = getattr(settings.agent, "system_prompt", "You are a helpful executive assistant.")

    w_id = workspace_id or "personal"

    # Inject available skills
    skills_context = _get_skills_context(user_id, w_id)

    # Inject workspace context
    workspace_context = _get_workspace_context(workspace_id)

    return base_prompt + skills_context + workspace_context + f"\n\nuser_id: {user_id}"


def _get_workspace_context(workspace_id: str | None) -> str:
    """Build workspace context for the system prompt."""
    if not workspace_id:
        return ""
    try:
        from src.sdk.workspace_models import load_workspace
        ws = load_workspace(workspace_id)
        if ws is None or ws.id == "personal":
            return ""
        lines = [f"\n\n## Current Workspace: {ws.name}"]
        if ws.custom_instructions:
            lines.append(ws.custom_instructions)
        return "\n".join(lines)
    except Exception:
        return ""


def _get_skills_context(user_id: str, workspace_id: str = "personal") -> str:
    """Build a concise skills reference for the system prompt."""
    try:
        from src.skills.registry import get_skill_registry

        registry = get_skill_registry(user_id=user_id, workspace_id=workspace_id)
        skills = registry.get_all_skills()
        if not skills:
            return ""

        visible_skills = [
            s
            for s in skills
            if str(s.get("metadata", {}).get("disable_model_invocation", "")).lower()
            not in ("true", "1", "yes")
        ]
        if not visible_skills:
            return ""

        lines = ["\n\n## Available Skills"]
        lines.append("When a task matches a skill description below, call skills_load(name) first to get detailed instructions before proceeding. Do NOT call skills_list — descriptions are already here.")
        lines.append("")
        for s in visible_skills:
            name = s.get("name", "")
            desc = s.get("description", "")
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)
    except Exception:
        return ""


async def create_sdk_loop(user_id: str, workspace_id: str = "personal", model: str | None = None, provider_keys: dict[str, str] | None = None) -> AgentLoop:
    """Create an AgentLoop for a user with all wiring."""
    import time

    _seed_default_workspace()
    t0 = time.monotonic()
    settings = get_settings()
    model_str = model or getattr(settings.agent, "model", "ollama:minimax-m2.5")

    provider = create_model_from_config(model_str, provider_keys=provider_keys)
    t1 = time.monotonic()

    tools = get_native_tools()
    t2 = time.monotonic()

    mcp_tools: list = []
    mcp_bridge = None
    try:
        from src.sdk.tools_core.mcp_bridge import MCPToolBridge

        mcp_bridge = MCPToolBridge(user_id=user_id)
        mcp_count = await mcp_bridge.discover()
        if mcp_count > 0:
            mcp_tools = mcp_bridge.get_tool_definitions()
            logger.info("sdk_runner.mcp_tools", {"count": mcp_count}, user_id=user_id)
    except Exception as e:
        logger.warning("sdk_runner.mcp_failed", {"error": str(e)}, user_id=user_id)

    connector_tools: list = []
    connectkit_bridge = None
    try:
        from connectkit.bridge import ConnectKitBridge

        connectkit_bridge = ConnectKitBridge(user_id=user_id)
        await connectkit_bridge.discover()
        connector_tools = connectkit_bridge.get_tool_definitions()
        if connector_tools:
            logger.info(
                "sdk_runner.connector_tools",
                {"count": len(connector_tools)},
                user_id=user_id,
            )
    except Exception as e:
        logger.warning(
            "sdk_runner.connector_failed", {"error": str(e)}, user_id=user_id
        )

    connectkit_tool_defs = _connector_dicts_to_defs(connector_tools)
    all_tools = tools + mcp_tools + connectkit_tool_defs
    t3 = time.monotonic()

    logger.info("sdk_runner.tools_loaded", {"count": len(all_tools)}, user_id=user_id)

    summary_config = settings.memory.summarization

    middlewares: list[Any] = []

    if summary_config.enabled:
        middlewares.append(
            SummarizationMiddleware(
                trigger_tokens=summary_config.trigger_tokens,
                keep_tokens=summary_config.keep_tokens,
                model=model_str,
            )
        )

    middlewares.append(
        ObservationMiddleware(user_id=user_id, workspace_id=workspace_id)
    )
    # middlewares.append(MemoryMiddleware(user_id=user_id, workspace_id=workspace_id))
    t4 = time.monotonic()

    loop = AgentLoop(
        provider=provider,
        tools=all_tools,
        system_prompt=_get_system_prompt(user_id, workspace_id),
        middlewares=middlewares,
        user_id=user_id,
        workspace_id=workspace_id,
    )

    if mcp_bridge:
        loop._mcp_bridge = mcp_bridge

    if connectkit_bridge:
        loop._connectkit_bridge = connectkit_bridge

    t5 = time.monotonic()
    logger.info(
        "sdk_runner.create_timing",
        {
            "provider": f"{t1-t0:.3f}s",
            "tools": f"{t2-t1:.3f}s",
            "mcp": f"{t3-t2:.3f}s",
            "middleware": f"{t4-t3:.3f}s",
            "agentloop": f"{t5-t4:.3f}s",
            "total": f"{t5-t0:.3f}s",
        },
        user_id=user_id,
    )

    return loop


async def get_sdk_loop(user_id: str, workspace_id: str = "personal", model: str | None = None, provider_keys: dict[str, str] | None = None) -> AgentLoop:
    """Get or create an AgentLoop for a user+workspace+model (cached)."""
    if provider_keys:
        loop = await create_sdk_loop(user_id, workspace_id, model=model, provider_keys=provider_keys)
        logger.info("sdk_runner.loop_created_uncached", {"user_id": user_id, "workspace_id": workspace_id, "model": model}, user_id=user_id)
        return loop
    cache_key = f"{user_id}:{workspace_id}:{model or 'default'}"
    async with _loop_lock:
        if cache_key not in _loop_cache:
            _loop_cache[cache_key] = await create_sdk_loop(user_id, workspace_id, model=model)
            logger.info("sdk_runner.loop_created", {"user_id": user_id, "workspace_id": workspace_id, "model": model}, user_id=user_id)
        return _loop_cache[cache_key]


def _connector_dicts_to_defs(dicts: list[dict]) -> list[ToolDefinition]:
    """Convert connectkit tool dicts to SDK ToolDefinition objects.

    Connector adapters produce plain dicts (to avoid depending on the EA SDK).
    This function converts them to proper ToolDefinition instances.
    """
    defs = []
    for d in dicts:
        annotations = ToolAnnotations(
            title=d.get("annotations", {}).get("title", d["name"]),
            read_only=d.get("annotations", {}).get("read_only", False),
            destructive=d.get("annotations", {}).get("destructive", False),
            idempotent=d.get("annotations", {}).get("idempotent", False),
        )
        func = d.get("function")
        ainvoke = d.get("ainvoke")

        td = ToolDefinition(
            name=d["name"],
            description=d["description"],
            parameters=d.get("parameters", {}),
            annotations=annotations,
            function=func,
        )
        if ainvoke:
            td._coroutine = ainvoke
        defs.append(td)
    return defs


def _messages_from_conversation(messages: list[Any]) -> list[Message]:
    """Convert conversation store messages to SDK Messages."""
    sdk_messages: list[Message] = []
    pending_reasoning: str | None = None
    for m in messages:
        role = getattr(m, "role", "user")
        content = getattr(m, "content", "")
        if role == "user":
            sdk_messages.append(Message.user(content))
            pending_reasoning = None
        elif role == "summary":
            sdk_messages.append(Message.user(f"[SUMMARY OF PREVIOUS CONVERSATION]\n{content}"))
            pending_reasoning = None
        elif role == "system":
            sdk_messages.append(Message.system(content))
            pending_reasoning = None
        elif role == "tool":
            meta = getattr(m, "metadata", {}) or {}
            tool_name = meta.get("tool_name") or meta.get("tool") or "unknown"
            tool_text = str(content or "")[:500]
            if tool_text:
                sdk_messages.append(Message.system(f"[Tool: {tool_name}] {tool_text}"))
            pending_reasoning = None
        elif role == "reasoning":
            pending_reasoning = content or None
        else:
            sdk_messages.append(
                Message.assistant(content, reasoning=pending_reasoning)
            )
            pending_reasoning = None
    return sdk_messages


async def run_sdk_agent(
    user_id: str,
    messages: list[Message],
    workspace_id: str = "personal",
    model: str | None = None,
    provider_keys: dict[str, str] | None = None,
) -> list[Message]:
    """Run the SDK agent loop to completion.

    Args:
        user_id: User identifier.
        messages: Conversation history as SDK Messages.
        workspace_id: Current workspace ID.
        model: Optional model override.
        provider_keys: Optional per-provider API keys from frontend.

    Returns:
        Final message list from the agent.
    """
    loop = await get_sdk_loop(user_id, workspace_id, model=model, provider_keys=provider_keys)
    result = await loop.run(messages)
    return result


async def run_sdk_agent_stream(
    user_id: str,
    messages: list[Message],
    workspace_id: str = "personal",
    model: str | None = None,
    provider_keys: dict[str, str] | None = None,
) -> Any:
    loop = await get_sdk_loop(user_id, workspace_id, model=model, provider_keys=provider_keys)

    try:
        async for chunk in loop.run_stream(messages):
            yield chunk
    except Exception as e:
        logger.error("sdk_runner.stream_error", {"error": str(e)}, user_id=user_id)
        yield StreamChunk.error(message=str(e))


def reset_sdk_loop(user_id: str = "default_user", workspace_id: str = "personal") -> None:
    """Reset the SDK agent loop for a user+workspace."""
    cache_prefix = f"{user_id}:{workspace_id}:"
    for cache_key in list(_loop_cache):
        if cache_key.startswith(cache_prefix):
            del _loop_cache[cache_key]
    from src.storage.memory import clear_memory_store_cache
    clear_memory_store_cache()
    logger.info("sdk_runner.loop_reset", {"user_id": user_id, "workspace_id": workspace_id}, user_id=user_id)


def reset_user_sdk_loops(user_id: str) -> None:
    """Reset all cached SDK agent loops for a user across workspaces."""
    cache_prefix = f"{user_id}:"
    for cache_key in list(_loop_cache):
        if cache_key.startswith(cache_prefix):
            del _loop_cache[cache_key]
    from src.storage.memory import clear_memory_store_cache
    clear_memory_store_cache()
    logger.info("sdk_runner.user_loops_reset", {"user_id": user_id}, user_id=user_id)


def reset_all_sdk_loops() -> None:
    """Reset all cached agent loops."""
    _loop_cache.clear()
    from src.storage.memory import clear_memory_store_cache
    clear_memory_store_cache()
    logger.info("sdk_runner.all_loops_reset", {})
