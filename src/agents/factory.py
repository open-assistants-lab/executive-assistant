"""Agent factory for Executive Assistant."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.config import get_settings
from src.llm import create_model_from_config


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

        if self.enable_summarization:
            settings = get_settings()
            summary_config = settings.memory.summarization

            if summary_config.enabled:
                middleware.append(
                    SummarizationMiddleware(
                        model=model,
                        trigger=("tokens", summary_config.trigger_tokens),
                        keep=("messages", summary_config.keep_messages),
                    )
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
