"""WebSocket protocol message types and serialization.

This module defines the bidirectional message protocol for the
/ws/conversation endpoint. It serves as the contract between
the frontend (Flutter, HTML test harness) and the backend.

The protocol is designed to be:
- Simple: JSON messages, typed, no binary frames
- Bidirectional: client sends messages, server streams responses
- Extensible: unknown types are ignored (forward compatibility)
"""

from pydantic import BaseModel, Field


# ─── Client → Server Messages ───


class UserMessage(BaseModel):
    """Client sends a chat message to the agent."""

    type: str = "user_message"
    content: str
    user_id: str = "default"
    verbose: bool = False


class ApproveMessage(BaseModel):
    """Client approves a pending tool call (HITL)."""

    type: str = "approve"
    call_id: str


class RejectMessage(BaseModel):
    """Client rejects a pending tool call (HITL)."""

    type: str = "reject"
    call_id: str
    reason: str = ""


class EditAndApproveMessage(BaseModel):
    """Client edits tool call arguments and approves (HITL)."""

    type: str = "edit_and_approve"
    call_id: str
    edited_args: dict


class CancelMessage(BaseModel):
    """Client cancels an ongoing agent execution."""

    type: str = "cancel"


class PingMessage(BaseModel):
    """Client sends heartbeat."""

    type: str = "ping"


# ─── Server → Client Messages ───


class AiTokenMessage(BaseModel):
    """Streaming AI text token."""

    type: str = "ai_token"
    content: str
    session_id: str = ""


class ToolStartMessage(BaseModel):
    """Tool call started."""

    type: str = "tool_start"
    tool: str
    call_id: str
    args: dict = Field(default_factory=dict)


class ToolEndMessage(BaseModel):
    """Tool call completed."""

    type: str = "tool_end"
    tool: str
    call_id: str
    result_preview: str = ""


class InterruptMessage(BaseModel):
    """Agent requests human approval for a tool call."""

    type: str = "interrupt"
    call_id: str
    tool: str
    args: dict = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=lambda: ["approve", "reject", "edit"])


class MiddlewareMessage(BaseModel):
    """Middleware event (verbose mode)."""

    type: str = "middleware"
    name: str
    event: str
    data: dict = Field(default_factory=dict)


class ReasoningMessage(BaseModel):
    """Reasoning/thinking token (for reasoning models)."""

    type: str = "reasoning"
    content: str
    session_id: str = ""


class DoneMessage(BaseModel):
    """Agent execution complete."""

    type: str = "done"
    response: str = ""
    tool_calls: list[dict] = Field(default_factory=list)


class ErrorMessage(BaseModel):
    """Error from the agent."""

    type: str = "error"
    message: str
    code: str = "AGENT_ERROR"


class PongMessage(BaseModel):
    """Server heartbeat response."""

    type: str = "pong"


# ─── Message Parsing ───

CLIENT_MESSAGE_TYPES = {
    "user_message": UserMessage,
    "approve": ApproveMessage,
    "reject": RejectMessage,
    "edit_and_approve": EditAndApproveMessage,
    "cancel": CancelMessage,
    "ping": PingMessage,
}

SERVER_MESSAGE_TYPES = {
    "ai_token": AiTokenMessage,
    "tool_start": ToolStartMessage,
    "tool_end": ToolEndMessage,
    "interrupt": InterruptMessage,
    "middleware": MiddlewareMessage,
    "reasoning": ReasoningMessage,
    "done": DoneMessage,
    "error": ErrorMessage,
    "pong": PongMessage,
}


def parse_client_message(
    data: dict,
) -> (
    UserMessage
    | ApproveMessage
    | RejectMessage
    | EditAndApproveMessage
    | CancelMessage
    | PingMessage
    | None
):
    """Parse a client message from raw dict. Returns None for unknown types."""
    msg_type = data.get("type", "")
    msg_cls = CLIENT_MESSAGE_TYPES.get(msg_type)
    if msg_cls is None:
        return None
    try:
        return msg_cls(**data)
    except Exception:
        return None


def parse_server_message(
    data: dict,
) -> (
    AiTokenMessage
    | ToolStartMessage
    | ToolEndMessage
    | InterruptMessage
    | MiddlewareMessage
    | ReasoningMessage
    | DoneMessage
    | ErrorMessage
    | PongMessage
    | None
):
    """Parse a server message from raw dict. Returns None for unknown types."""
    msg_type = data.get("type", "")
    msg_cls = SERVER_MESSAGE_TYPES.get(msg_type)
    if msg_cls is None:
        return None
    try:
        return msg_cls(**data)
    except Exception:
        return None
