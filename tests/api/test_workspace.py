"""Contract tests for workspace/file endpoints."""

from src.storage.messages import get_message_store


class TestWorkspaceDeletionAndRecreation:
    """Workspace deletion must clean up messages; recreation must produce blank slate."""

    def test_delete_workspace_removes_messages(self, client, test_user_id):
        ws_name = "LLM"
        workspace_id = "llm"

        r = client.post("/workspaces", json={"name": ws_name})
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == workspace_id

        store = get_message_store(test_user_id, workspace_id)
        store.add_message("user", "Hello, this is a test message.", metadata={"workspace_id": workspace_id})
        store.add_message("assistant", "Hi, I am an assistant.", metadata={"workspace_id": workspace_id})

        r = client.get("/conversation", params={"user_id": test_user_id, "workspace_id": workspace_id})
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert len(msgs) == 2, f"Expected 2 messages before delete, got {len(msgs)}"

        r = client.delete(f"/workspaces/{workspace_id}", params={"user_id": test_user_id})
        assert r.status_code == 200

        r = client.post("/workspaces", json={"name": ws_name})
        assert r.status_code == 200
        new_data = r.json()
        assert new_data["id"] == workspace_id

        r = client.get(
            "/conversation",
            params={"user_id": test_user_id, "workspace_id": workspace_id, "limit": 50},
        )
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert len(msgs) == 0, (
            f"Expected 0 messages after delete+recreate, got {len(msgs)}. "
            "Messages from old workspace should not reappear."
        )


class TestWorkspaceFiles:
    """Tests for workspace file endpoints."""

    def test_list_workspace_root(self, client, test_user_id):
        r = client.get("/workspace", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_list_workspace_subpath(self, client, test_user_id):
        r = client.get("/workspace/documents", params={"user_id": test_user_id})
        assert r.status_code == 200


class TestFileSync:
    """Tests for file sync endpoints."""

    def test_get_sync_status(self, client, test_user_id):
        r = client.get("/sync/status", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_pin_file(self, client, test_user_id):
        r = client.post("/sync/pin/test_file.txt", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_unpin_file(self, client, test_user_id):
        r = client.delete("/sync/pin/test_file.txt", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_mark_downloaded(self, client, test_user_id):
        r = client.post("/sync/download/test_file.txt", params={"user_id": test_user_id})
        assert r.status_code == 200
