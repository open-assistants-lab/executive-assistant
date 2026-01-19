"""LangChain agent state schema extensions."""

from typing import Any
from typing_extensions import NotRequired

from langchain.agents import AgentState as BaseAgentState

from cassey.agent.state import AgentState as TaskState


class CasseyAgentState(BaseAgentState[Any]):
    """AgentState extended with task_state."""

    task_state: NotRequired[TaskState]
