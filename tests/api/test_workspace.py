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

    def test_clear_conversation_only_clears_requested_workspace(self, client, test_user_id):
        personal = get_message_store(test_user_id, "personal")
        project = get_message_store(test_user_id, "project")
        personal.add_message("user", "personal message", metadata={"workspace_id": "personal"})
        project.add_message("user", "project message", metadata={"workspace_id": "project"})

        r = client.delete(
            "/conversation",
            params={"user_id": test_user_id, "workspace_id": "project"},
        )
        assert r.status_code == 200

        r = client.get("/conversation", params={"user_id": test_user_id, "workspace_id": "personal"})
        assert [m["content"] for m in r.json()["messages"]] == ["personal message"]

        r = client.get("/conversation", params={"user_id": test_user_id, "workspace_id": "project"})
        assert r.json()["messages"] == []


class TestWorkspaceFiles:
    """Tests for workspace file endpoints."""

    def test_list_workspace_root(self, client, test_user_id):
        r = client.get("/workspace", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_list_workspace_subpath(self, client, test_user_id):
        r = client.get("/workspace/documents", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_file_routes_honor_workspace_id(self, client, test_user_id):
        project_params = {"user_id": test_user_id, "workspace_id": "project"}
        personal_params = {"user_id": test_user_id, "workspace_id": "personal"}
        filename = f"note_{test_user_id}.txt"

        r = client.post(f"/workspace/{filename}", params=project_params, json={"content": "project-only"})
        assert r.status_code == 200

        r = client.get(f"/workspace/read/{filename}", params=project_params)
        assert r.status_code == 200
        assert "project-only" in r.json()["response"]

        r = client.get(f"/workspace/read/{filename}", params=personal_params)
        assert r.status_code == 200
        assert "File not found" in r.json()["response"]


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
