"""SDK Agent Runner — creates and runs AgentLoop with proper wiring.

This is the bridge between the HTTP layer and the SDK AgentLoop.
It handles:
  - Creating LLM provider from config
  - Loading SDK-native tools (no more LangChain adapter)
  - Loading MCP tools via MCPToolBridge
  - Loading SaaS connector tools via AgentConnectBridge
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
from src.sdk.middleware_memory import MemoryMiddleware
from src.sdk.middleware_summarization import SummarizationMiddleware
from src.sdk.native_tools import get_native_tools
from src.sdk.providers.factory import create_model_from_config
from src.sdk.tools import ToolAnnotations, ToolDefinition, ToolResult

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

    # Inject available skills
    skills_context = _get_skills_context(user_id)

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


def _get_skills_context(user_id: str) -> str:
    """Build a concise skills reference for the system prompt."""
    try:
        from src.skills.registry import get_skill_registry

        registry = get_skill_registry(user_id=user_id)
        skills = registry.get_all_skills()
        if not skills:
            return ""

        lines = ["\n\n## Available Skills"]
        lines.append("When a task matches a skill description below, call skills_load(name) first to get detailed instructions before proceeding. Do NOT call skills_list — descriptions are already here.")
        lines.append("")
        for s in skills:
            name = s.get("name", "")
            desc = s.get("description", "")
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)
    except Exception:
        return ""


async def create_sdk_loop(user_id: str) -> AgentLoop:
    """Create an AgentLoop for a user with all wiring.

    All tools are now SDK-native (from src.sdk.native_tools).
    MCP tools are discovered and injected via MCPToolBridge.
    No more LangChain adapter needed.
    """
    import time

    # Auto-seed default workspace on first launch
    _seed_default_workspace()

    t0 = time.monotonic()
    settings = get_settings()
    model_str = getattr(settings.agent, "model", "ollama:minimax-m2.5")

    provider = create_model_from_config(model_str)
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
    connector_bridge = None
    try:
        from agent_connect.bridge import AgentConnectBridge

        connector_bridge = AgentConnectBridge(user_id=user_id)
        await connector_bridge.discover()
        connector_tools = connector_bridge.get_tool_definitions()
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

    # Convert connector dicts to ToolDefinitions
    connector_tool_defs = _connector_dicts_to_defs(connector_tools)

    all_tools = tools + mcp_tools + connector_tool_defs
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

    middlewares.append(MemoryMiddleware(user_id=user_id))
    t4 = time.monotonic()

    loop = AgentLoop(
        provider=provider,
        tools=all_tools,
        system_prompt=_get_system_prompt(user_id),
        middlewares=middlewares,
        user_id=user_id,
    )

    if mcp_bridge:
        loop._mcp_bridge = mcp_bridge

    if connector_bridge:
        loop._connector_bridge = connector_bridge

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


async def get_sdk_loop(user_id: str) -> AgentLoop:
    """Get or create an AgentLoop for a user (cached)."""
    async with _loop_lock:
        if user_id not in _loop_cache:
            _loop_cache[user_id] = await create_sdk_loop(user_id)
            logger.info("sdk_runner.loop_created", {"user_id": user_id}, user_id=user_id)
        return _loop_cache[user_id]


def _connector_dicts_to_defs(dicts: list[dict]) -> list[ToolDefinition]:
    """Convert connector tool dicts to SDK ToolDefinition objects.

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
            # Tool metadata is for audit/display, not LLM context
            continue
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
) -> list[Message]:
    """Run the SDK agent loop to completion.

    Args:
        user_id: User identifier.
        messages: Conversation history as SDK Messages.

    Returns:
        Final message list from the agent.
    """
    loop = await get_sdk_loop(user_id)
    result = await loop.run(messages)
    return result


async def run_sdk_agent_stream(
    user_id: str,
    messages: list[Message],
    workspace_id: str | None = None,
) -> Any:
    """Run the SDK agent loop with streaming.

    Yields StreamChunk events that map directly to WS protocol messages.

    Args:
        user_id: User identifier.
        messages: Conversation history as SDK Messages.
        workspace_id: Current workspace ID for context injection.

    Yields:
        StreamChunk events.
    """
    loop = await get_sdk_loop(user_id)

    # Inject workspace context into the first system message if present
    if workspace_id:
        ctx = _get_workspace_context(workspace_id)
        if ctx and messages:
            for i, m in enumerate(messages):
                if m.role == "system":
                    messages[i] = Message.system(m.content + ctx)
                    break

    try:
        async for chunk in loop.run_stream(messages):
            yield chunk
    except Exception as e:
        logger.error("sdk_runner.stream_error", {"error": str(e)}, user_id=user_id)
        yield StreamChunk.error(message=str(e))


def reset_sdk_loop(user_id: str = "default_user") -> None:
    """Reset the SDK agent loop for a user."""
    if user_id in _loop_cache:
        del _loop_cache[user_id]
    logger.info("sdk_runner.loop_reset", {"user_id": user_id}, user_id=user_id)


def reset_all_sdk_loops() -> None:
    """Reset all cached agent loops."""
    _loop_cache.clear()
    logger.info("sdk_runner.all_loops_reset", {})
