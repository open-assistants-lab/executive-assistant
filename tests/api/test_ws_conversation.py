"""Tests for WebSocket conversation runtime behavior."""

from src.http.routers.conversation import _filter_by_workspace
from src.sdk.messages import StreamChunk


class _StoredMessage:
    def __init__(self, content, metadata=None):
        self.content = content
        self.metadata = metadata


def test_filter_personal_excludes_other_workspace_messages():
    messages = [
        _StoredMessage("legacy", None),
        _StoredMessage("personal", {"workspace_id": "personal"}),
        _StoredMessage("test 12", {"workspace_id": "test-12"}),
    ]

    filtered = _filter_by_workspace(messages, "personal")

    assert [m.content for m in filtered] == ["legacy", "personal"]


def test_ws_user_message_sent_to_agent_once(client, monkeypatch, test_user_id):
    seen_messages = []

    async def fake_run_sdk_agent_stream(**kwargs):
        seen_messages.extend(kwargs["messages"])
        yield StreamChunk.done("ok")

    monkeypatch.setattr(
        "src.http.routers.ws.run_sdk_agent_stream", fake_run_sdk_agent_stream
    )

    with client.websocket_connect("/ws/conversation") as websocket:
        websocket.send_json(
            {
                "type": "user_message",
                "content": "hello once",
                "user_id": test_user_id,
                "workspace_id": "ws-test",
            }
        )

        while True:
            msg = websocket.receive_json()
            if msg["type"] == "done":
                break

    user_contents = [m.content for m in seen_messages if m.role == "user"]
    assert user_contents.count("hello once") == 1


def test_ws_messages_persist_with_workspace_metadata(client, monkeypatch, test_user_id):
    async def fake_run_sdk_agent_stream(**kwargs):
        yield StreamChunk.text_delta("assistant reply")
        yield StreamChunk.done("assistant reply")

    monkeypatch.setattr(
        "src.http.routers.ws.run_sdk_agent_stream", fake_run_sdk_agent_stream
    )

    with client.websocket_connect("/ws/conversation") as websocket:
        websocket.send_json(
            {
                "type": "user_message",
                "content": "persist me",
                "user_id": test_user_id,
                "workspace_id": "ws-test-12",
            }
        )

        while True:
            msg = websocket.receive_json()
            if msg["type"] == "done":
                break

    response = client.get(
        "/conversation",
        params={"user_id": test_user_id, "workspace_id": "ws-test-12", "limit": 10},
    )
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [m["content"] for m in messages] == ["persist me", "assistant reply"]
    assert all(m["metadata"]["workspace_id"] == "ws-test-12" for m in messages)
