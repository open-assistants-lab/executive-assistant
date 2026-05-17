"""Contract tests for subagent V1 endpoints."""


class TestSubagentsEndpoints:
    def test_list_subagents(self, client, test_user_id):
        r = client.get(
            "/subagents",
            params={"user_id": test_user_id, "workspace_id": "personal"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "subagents" in data

    def test_list_subagent_jobs(self, client, test_user_id):
        r = client.get(
            "/subagents/jobs",
            params={"user_id": test_user_id, "workspace_id": "personal"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data

    def test_get_subagent_job_not_found(self, client):
        r = client.get(
            "/subagents/jobs/nonexistent_job_id",
            params={"user_id": "test_user", "workspace_id": "personal"},
        )
        assert r.status_code == 404


class TestSubagentV1Invocations:
    def test_subagent_start_route(self, client):
        response = client.post(
            "/subagents/worker/start",
            params={"user_id": "test_user", "workspace_id": "personal"},
            json={"task": "do work"},
        )
        assert response.status_code in {200, 404}

    def test_old_invoke_route_removed(self, client):
        response = client.post("/subagents/invoke", params={"name": "worker", "task": "do work"})
        assert response.status_code == 404

    def test_cancel_subagent_job(self, client):
        r = client.post(
            "/subagents/jobs/nonexistent_job/cancel",
            params={"user_id": "test_user", "workspace_id": "personal"},
        )
        assert r.status_code == 404

    def test_job_instruction_route_exists(self, client):
        response = client.post(
            "/subagents/jobs/not-real/instructions",
            params={"user_id": "test_user", "workspace_id": "personal"},
            json={"instruction": "focus"},
        )
        assert response.status_code in {200, 404}

    def test_old_instruct_route_removed(self, client):
        response = client.post(
            "/subagents/instruct",
            params={"name": "worker", "instruction": "focus"},
        )
        assert response.status_code == 404

    def test_update_subagent(self, client, test_user_id):
        r = client.patch(
            "/subagents/nonexistent_agent",
            json={"tools": ["web_search"]},
            params={"user_id": test_user_id, "workspace_id": "personal"},
        )
        assert r.status_code in (200, 404)

    def test_delete_subagent(self, client, test_user_id):
        r = client.delete(
            "/subagents/nonexistent_agent",
            params={"user_id": test_user_id, "workspace_id": "personal"},
        )
        assert r.status_code in (200, 404)
