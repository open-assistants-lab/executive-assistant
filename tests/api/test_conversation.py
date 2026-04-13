"""Contract tests for conversation endpoints."""


class TestGetConversation:
    """Tests for GET /conversation."""

    def test_get_conversation_default_user(self, client):
        r = client.get("/conversation")
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_get_conversation_with_user_id(self, client, test_user_id):
        r = client.get("/conversation", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data

    def test_get_conversation_with_limit(self, client, test_user_id):
        r = client.get("/conversation", params={"user_id": test_user_id, "limit": 5})
        assert r.status_code == 200

    def test_get_conversation_response_schema(self, client, test_user_id):
        r = client.get("/conversation", params={"user_id": test_user_id})
        data = r.json()
        for msg in data["messages"]:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("user", "assistant", "tool", "summary")


class TestClearConversation:
    """Tests for DELETE /conversation."""

    def test_clear_conversation(self, client, test_user_id):
        r = client.delete("/conversation", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cleared"
        assert data["user_id"] == test_user_id

    def test_clear_conversation_default_user(self, client):
        r = client.delete("/conversation")
        assert r.status_code == 200
