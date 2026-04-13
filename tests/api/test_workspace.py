"""Contract tests for workspace/file endpoints."""


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
