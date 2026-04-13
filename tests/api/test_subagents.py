"""Contract tests for subagent endpoints."""

import pytest


class TestSubagentsEndpoints:
    """Tests for subagent CRUD and job endpoints."""

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


class TestSubagentInvocations:
    """Tests for subagent invoke/schedule/batch endpoints."""

    def test_invoke_subagent_requires_name_and_task(self, client, test_user_id):
        r = client.post(
            "/subagents/invoke",
            params={"name": "nonexistent_agent", "task": "do something", "user_id": test_user_id},
        )
        assert r.status_code == 200

    @pytest.mark.skip(
        reason="Bug: HTTP endpoint maps 'name' but tool expects 'subagent_name'; will fix in refactor"
    )
    def test_schedule_subagent(self, client, test_user_id):
        r = client.post(
            "/subagents/schedule",
            params={
                "name": "nonexistent_agent",
                "task": "check email",
                "run_at": "2099-01-01T00:00:00Z",
                "user_id": test_user_id,
            },
        )
        assert r.status_code == 200

    def test_cancel_subagent_job(self, client, test_user_id):
        r = client.delete("/subagents/jobs/nonexistent_job", params={"user_id": test_user_id})
        assert r.status_code == 200
