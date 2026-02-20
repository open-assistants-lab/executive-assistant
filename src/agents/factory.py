"""Agent factory for Executive Assistant."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver


class AgentFactory:
    """Factory for creating Executive Assistant agents."""

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver | None = None,
    ):
        """Initialize agent factory.

        Args:
            checkpointer: LangGraph checkpointer for conversation persistence
        """
        self.checkpointer = checkpointer

    def create(
        self,
        model: BaseChatModel,
        tools: Sequence[Any] | None = None,
        system_prompt: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> Any:
        """Create an agent using LangChain create_agent().

        Args:
            model: Chat model to use
            tools: List of tools available to the agent
            system_prompt: System prompt for the agent
            checkpointer: Optional checkpointer for conversation persistence

        Returns:
            Compiled LangGraph agent
        """
        effective_checkpointer = checkpointer or self.checkpointer

        agent = create_agent(
            model=model,
            tools=tools or [],
            system_prompt=system_prompt,
            checkpointer=effective_checkpointer,
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
) -> AgentFactory:
    """Get or create agent factory.

    Args:
        checkpointer: Default checkpointer for all agents

    Returns:
        AgentFactory instance
    """
    return AgentFactory(checkpointer=checkpointer)
