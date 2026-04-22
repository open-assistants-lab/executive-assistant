"""Tests for SDK AgentState."""



from src.sdk.messages import Message
from src.sdk.state import AgentState


class TestAgentState:
    def test_default_empty(self):
        state = AgentState()
        assert state.messages == []
        assert state.extra == {}

    def test_add_message(self):
        state = AgentState()
        state.add_message(Message.user("Hello"))
        assert len(state.messages) == 1
        assert state.messages[0].content == "Hello"

    def test_last_message(self):
        state = AgentState()
        assert state.last_message() is None
        state.add_message(Message.user("First"))
        state.add_message(Message.assistant("Second"))
        assert state.last_message().content == "Second"

    def test_message_count(self):
        state = AgentState()
        assert state.message_count() == 0
        state.add_message(Message.user("Hi"))
        assert state.message_count() == 1

    def test_user_messages(self):
        state = AgentState()
        state.add_message(Message.system("System"))
        state.add_message(Message.user("Hello"))
        state.add_message(Message.assistant("Hi"))
        state.add_message(Message.user("How are you?"))
        assert len(state.user_messages()) == 2

    def test_assistant_messages(self):
        state = AgentState()
        state.add_message(Message.user("Hi"))
        state.add_message(Message.assistant("Hello"))
        state.add_message(Message.assistant("How can I help?"))
        assert len(state.assistant_messages()) == 2

    def test_tool_results(self):
        state = AgentState()
        state.add_message(Message.tool_result("c1", "3pm", name="time_get"))
        state.add_message(Message.user("Thanks"))
        assert len(state.tool_results()) == 1

    def test_system_message(self):
        state = AgentState()
        assert state.system_message() is None
        state.add_message(Message.system("You are helpful"))
        assert state.system_message().content == "You are helpful"

    def test_extra_get_set(self):
        state = AgentState()
        assert state.get("key") is None
        assert state.get("key", "default") == "default"
        state.set("key", "value")
        assert state.get("key") == "value"

    def test_update_messages(self):
        state = AgentState()
        new_msgs = [Message.user("Hello")]
        state.update({"messages": new_msgs})
        assert len(state.messages) == 1
        assert state.messages[0].content == "Hello"

    def test_update_extra(self):
        state = AgentState()
        state.update({"extra": {"key1": "val1"}})
        assert state.extra["key1"] == "val1"

    def test_update_key(self):
        state = AgentState()
        state.update({"turn_count": 5})
        assert state.get("turn_count") == 5

    def test_to_dict(self):
        state = AgentState()
        state.add_message(Message.user("Hello"))
        state.set("count", 3)
        d = state.to_dict()
        assert len(d["messages"]) == 1
        assert d["extra"]["count"] == 3

    def test_from_dict(self):
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "tool_calls": [],
                    "tool_call_id": None,
                    "name": None,
                }
            ],
            "extra": {"count": 3},
        }
        state = AgentState.from_dict(data)
        assert len(state.messages) == 1
        assert state.messages[0].role == "user"
        assert state.get("count") == 3

    def test_roundtrip(self):
        state = AgentState()
        state.add_message(Message.system("Be helpful"))
        state.add_message(Message.user("Hi"))
        state.set("turn", 1)
        restored = AgentState.from_dict(state.to_dict())
        assert len(restored.messages) == 2
        assert restored.get("turn") == 1
