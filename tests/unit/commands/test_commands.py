from __future__ import annotations

from src.commands import handle_clear_command


def test_handle_clear_command_uses_provided_thread_id() -> None:
    message = handle_clear_command(user_id="user-1", thread_id="api-user-1-clear-abc")
    assert "Conversation history cleared." in message
    assert "api-user-1-clear-abc" in message
