"""Agent factory for Executive Assistant."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.agents.middleware.summarization import SummarizationMiddleware
from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


class AgentFactory:
    """Factory for creating Executive Assistant agents."""

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver | None = None,
        enable_summarization: bool = True,
        enable_skills: bool = True,
        enable_mcp: bool = True,
        user_id: str | None = None,
        on_summarize: Callable[[str], Any] | None = None,
    ):
        """Initialize agent factory.

        Args:
            checkpointer: LangGraph checkpointer for conversation persistence
            enable_summarization: Whether to enable summarization middleware
            enable_skills: Whether to enable skills middleware and tools
            enable_mcp: Whether to enable MCP tools
            user_id: User ID for loading user-specific skills
            on_summarize: Callback when summarization occurs, receives summary content
        """
        self.checkpointer = checkpointer
        self.enable_summarization = enable_summarization
        self.enable_skills = enable_skills
        self.enable_mcp = enable_mcp
        self.user_id = user_id
        self._on_summarize = on_summarize

    def _get_middleware(self, model: BaseChatModel) -> list[Any]:
        """Get middleware list for the agent."""
        middleware = []
        settings = get_settings()

        # Summarization middleware
        if self.enable_summarization:
            summary_config = settings.memory.summarization

            if summary_config.enabled:
                middleware.append(
                    SummarizationMiddleware(
                        model=model,
                        trigger=("tokens", summary_config.trigger_tokens),
                        keep=("tokens", summary_config.keep_tokens),
                        on_summarize=self._on_summarize,
                    )
                )
                logger.info(
                    "summarization.middleware.configured",
                    {
                        "trigger_tokens": summary_config.trigger_tokens,
                        "keep_tokens": summary_config.keep_tokens,
                        "model": str(model),
                        "has_callback": self._on_summarize is not None,
                    },
                    channel="agent",
                )

        # HITL middleware for filesystem delete
        filesystem_config = settings.filesystem

        # Build interrupt config for tools requiring approval
        interrupt_config = {}

        # Add filesystem delete tool
        if filesystem_config.enabled:
            interrupt_config["files_delete"] = {
                "allowed_decisions": ["approve", "edit", "reject"],
            }

        if interrupt_config:
            middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_config))
            logger.info(
                "hitl.middleware.configured",
                {"interrupt_on": list(interrupt_config.keys())},
                channel="agent",
            )

        return middleware

    def create(
        self,
        model: BaseChatModel,
        tools: Sequence[Any] | None = None,
        system_prompt: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        enable_summarization: bool | None = None,
        enable_skills: bool | None = None,
    ) -> Any:
        """Create an agent using LangChain create_agent().

        Args:
            model: Chat model to use
            tools: List of tools available to the agent
            system_prompt: System prompt for the agent
            checkpointer: Optional checkpointer for conversation persistence
            enable_summarization: Override summarization setting
            enable_skills: Override skills setting

        Returns:
            Compiled LangGraph agent
        """
        effective_checkpointer = checkpointer or self.checkpointer

        if enable_summarization is None:
            enable_summarization = self.enable_summarization
        if enable_skills is None:
            enable_skills = self.enable_skills

        # For MCP, use instance attribute
        enable_mcp = self.enable_mcp

        middleware = []
        if enable_summarization:
            middleware = self._get_middleware(model)

        # Always add skill middleware when enabled (regardless of summarization)
        if enable_skills:
            from src.skills import SkillMiddleware, SkillRegistry, set_skill_registry

            system_dir = "src/skills"  # Fixed system skills directory

            # Set up skill registry with user_id if available
            if self.user_id:
                set_skill_registry(
                    SkillRegistry(
                        system_dir=system_dir,
                        user_id=self.user_id,
                    )
                )

            middleware.append(SkillMiddleware(system_dir=system_dir, user_id=self.user_id))
            logger.info(
                "skill.middleware.configured",
                {"system_dir": system_dir, "user_id": self.user_id},
                channel="agent",
            )

        # Add memory middleware
        from src.storage.middleware import MemoryMiddleware

        middleware.append(MemoryMiddleware(user_id=self.user_id))
        logger.info(
            "memory.middleware.configured",
            {"user_id": self.user_id},
            channel="agent",
        )

        # Add skill tools
        all_tools = list(tools) if tools else []
        if enable_skills:
            from src.skills import skills_list, skills_load

            all_tools = list(all_tools) + [skills_load, skills_list]

        # Add memory tools
        from src.tools.memory_profile import (
            memory_list,
            memory_remove,
            memory_search,
            profile_set,
        )

        all_tools = list(all_tools) + [
            profile_set,
            memory_list,
            memory_remove,
            memory_search,
        ]

        # Add MCP management tools + dynamically load MCP server tools
        if enable_mcp and self.user_id:
            from src.tools.mcp.manager import get_mcp_manager
            from src.tools.mcp.tools import mcp_list, mcp_reload, mcp_tools

            all_tools = list(all_tools) + [mcp_list, mcp_reload, mcp_tools]

            # Load MCP server tools (triggers lazy start)
            try:
                import asyncio
                import concurrent.futures

                mcp_manager = get_mcp_manager(self.user_id)

                async def _load_mcp_tools():
                    return await mcp_manager.get_tools()

                # Run in thread pool to avoid event loop issues
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop - use asyncio.run directly
                    mcp_server_tools = asyncio.run(_load_mcp_tools())
                else:
                    # There's a running loop - use thread pool
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _load_mcp_tools())
                        mcp_server_tools = future.result()

                all_tools = list(all_tools) + mcp_server_tools
                logger.info(
                    "mcp.tools_loaded",
                    {"user_id": self.user_id, "count": len(mcp_server_tools)},
                    channel="agent",
                )
            except Exception as e:
                logger.warning(
                    "mcp.tools_load_error",
                    {"user_id": self.user_id, "error": str(e), "error_type": type(e).__name__},
                    channel="agent",
                )

        agent = create_agent(
            model=model,
            tools=all_tools,
            system_prompt=system_prompt,
            checkpointer=effective_checkpointer,
            middleware=middleware if middleware else [],
        )

        return agent


def get_agent_factory(
    checkpointer: BaseCheckpointSaver | None = None,
    enable_summarization: bool = True,
    enable_skills: bool = True,
    enable_mcp: bool = True,
    user_id: str | None = None,
    on_summarize: Callable[[str], Any] | None = None,
) -> AgentFactory:
    """Get or create agent factory.

    Args:
        checkpointer: Default checkpointer for all agents
        enable_summarization: Whether to enable summarization middleware
        enable_skills: Whether to enable skills middleware and tools
        user_id: User ID for loading user-specific skills
        on_summarize: Callback when summarization occurs

    Returns:
        AgentFactory instance
    """
    return AgentFactory(
        checkpointer=checkpointer,
        enable_summarization=enable_summarization,
        enable_skills=enable_skills,
        enable_mcp=enable_mcp,
        user_id=user_id,
        on_summarize=on_summarize,
    )
