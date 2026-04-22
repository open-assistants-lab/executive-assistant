"""Contract tests for subagent V1 endpoints."""


class TestSubagentsEndpoints:
    def test_list_subagents(self, client, test_user_id):
        r = client.get("/subagents", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "subagents" in data

    def test_list_subagent_jobs(self, client, test_user_id):
        r = client.get("/subagents/jobs", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data

    def test_get_subagent_job_not_found(self, client):
        r = client.get("/subagents/jobs/nonexistent_job_id")
        assert r.status_code in (200, 404)


class TestSubagentV1Invocations:
    def test_invoke_subagent_requires_name_and_task(self, client, test_user_id):
        r = client.post(
            "/subagents/invoke",
            params={"name": "nonexistent_agent", "task": "do something", "user_id": test_user_id},
        )
        assert r.status_code == 200

    def test_cancel_subagent_job(self, client, test_user_id):
        r = client.delete("/subagents/jobs/nonexistent_job", params={"user_id": test_user_id})
        assert r.status_code == 200

    def test_instruct_subagent(self, client, test_user_id):
        r = client.post(
            "/subagents/instruct",
            params={"name": "nonexistent_agent", "instruction": "also check arxiv", "user_id": test_user_id},
        )
        assert r.status_code in (200, 404)

    def test_update_subagent(self, client, test_user_id):
        r = client.patch(
            "/subagents/nonexistent_agent",
            json={"allowed_tools": ["search_web"]},
            params={"user_id": test_user_id},
        )
        assert r.status_code in (200, 404)

    def test_delete_subagent(self, client, test_user_id):
        r = client.delete("/subagents/nonexistent_agent", params={"user_id": test_user_id})
        assert r.status_code in (200, 404)
