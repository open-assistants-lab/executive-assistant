"""Agent state definition for ReAct graph."""

from typing import Annotated, NotRequired, Sequence, TypedDict

from langchain.agents.middleware.todo import Todo
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State that flows through all nodes in the ReAct agent graph.

    Attributes:
        messages: Accumulated message history with add_messages reducer.
        user_id: Thread identifier (channel + channel user id).
        channel: Source channel (telegram, slack, whatsapp, etc.).
        todos: List of todo items for tracking task progress (from TodoListMiddleware).
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    channel: str
    todos: NotRequired[list[Todo]]
