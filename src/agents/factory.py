"""Agent factory for Executive Assistant."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    SummarizationMiddleware,
)
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
        enable_skills: bool = True,
        user_id: str | None = None,
    ):
        """Initialize agent factory.

        Args:
            checkpointer: LangGraph checkpointer for conversation persistence
            enable_summarization: Whether to enable summarization middleware
            enable_skills: Whether to enable skills middleware and tools
            user_id: User ID for loading user-specific skills
        """
        self.checkpointer = checkpointer
        self.enable_summarization = enable_summarization
        self.enable_skills = enable_skills
        self.user_id = user_id

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

        # HITL middleware for filesystem delete
        filesystem_config = settings.filesystem

        # Build interrupt config for tools requiring approval
        interrupt_config = {}

        # Add filesystem delete tool
        if filesystem_config.enabled:
            interrupt_config["delete_file"] = {
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

        middleware = []
        if enable_summarization:
            middleware = self._get_middleware(model)

        # Always add skill middleware when enabled (regardless of summarization)
        if enable_skills:
            from src.skills import SkillMiddleware, SkillRegistry, set_skill_registry

            settings = get_settings()
            system_dir = settings.skills.directory

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

        # Add skill tools
        all_tools = list(tools) if tools else []
        if enable_skills:
            from src.skills import skills_list, skills_load

            all_tools = list(all_tools) + [skills_load, skills_list]

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
    user_id: str | None = None,
) -> AgentFactory:
    """Get or create agent factory.

    Args:
        checkpointer: Default checkpointer for all agents
        enable_summarization: Whether to enable summarization middleware
        enable_skills: Whether to enable skills middleware and tools
        user_id: User ID for loading user-specific skills

    Returns:
        AgentFactory instance
    """
    return AgentFactory(
        checkpointer=checkpointer,
        enable_summarization=enable_summarization,
        enable_skills=enable_skills,
        user_id=user_id,
    )
