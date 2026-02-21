"""Agent factory for Executive Assistant."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


class AgentFactory:
    """Factory for creating Executive Assistant agents."""

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver | None = None,
        enable_summarization: bool = True,
    ):
        """Initialize agent factory.

        Args:
            checkpointer: LangGraph checkpointer for conversation persistence
            enable_summarization: Whether to enable summarization middleware
        """
        self.checkpointer = checkpointer
        self.enable_summarization = enable_summarization

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
                        keep=("messages", summary_config.keep_messages),
                    )
                )
                logger.info(
                    "summarization.middleware.configured",
                    {
                        "trigger_tokens": summary_config.trigger_tokens,
                        "keep_messages": summary_config.keep_messages,
                        "model": str(model),
                    },
                    channel="agent",
                )

        # HITL middleware for filesystem delete and shell commands
        filesystem_config = settings.filesystem
        shell_config = settings.shell_tool

        # Build interrupt config for tools requiring approval
        interrupt_config = {}

        # Add filesystem delete tool
        if filesystem_config.enabled:
            interrupt_config["delete_file"] = {
                "allowed_decisions": ["approve", "edit", "reject"],
            }

        # Add shell hitl commands
        if shell_config.enabled and shell_config.hitl_commands:
            # For now, just enable HITL on run_shell for dangerous commands
            interrupt_config["run_shell"] = {
                "allowed_decisions": ["approve", "reject"],
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
    ) -> Any:
        """Create an agent using LangChain create_agent().

        Args:
            model: Chat model to use
            tools: List of tools available to the agent
            system_prompt: System prompt for the agent
            checkpointer: Optional checkpointer for conversation persistence
            enable_summarization: Override summarization setting

        Returns:
            Compiled LangGraph agent
        """
        effective_checkpointer = checkpointer or self.checkpointer

        if enable_summarization is None:
            enable_summarization = self.enable_summarization

        middleware = []
        if enable_summarization:
            middleware = self._get_middleware(model)

        agent = create_agent(
            model=model,
            tools=tools or [],
            system_prompt=system_prompt,
            checkpointer=effective_checkpointer,
            middleware=middleware if middleware else [],
        )

        return agent

    def create_with_default_tools(
        self,
        model: BaseChatModel,
        tools: Sequence[Any] | None = None,
        system_prompt: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> Any:
        """Create agent with default tools.

        Args:
            model: Chat model to use
            tools: Additional tools to add
            system_prompt: System prompt
            checkpointer: Optional checkpointer override

        Returns:
            Compiled agent
        """
        return self.create(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
        )


def get_agent_factory(
    checkpointer: BaseCheckpointSaver | None = None,
    enable_summarization: bool = True,
) -> AgentFactory:
    """Get or create agent factory.

    Args:
        checkpointer: Default checkpointer for all agents
        enable_summarization: Whether to enable summarization middleware

    Returns:
        AgentFactory instance
    """
    return AgentFactory(
        checkpointer=checkpointer,
        enable_summarization=enable_summarization,
    )
