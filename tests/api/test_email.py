"""Contract tests for email endpoints.

GET  /emails              — list emails
GET  /emails/:id           — single email
GET  /emails/search?q=...  — search
POST /emails/sync          — trigger sync
"""


class TestEmails:
    """Tests for /emails endpoints."""

    def test_list_emails(self, client, test_user_id):
        r = client.get("/emails", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "emails" in data

    def test_get_email_not_found(self, client, test_user_id):
        r = client.get("/emails/nonexistent", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "error" in data or "email_id" in data

    def test_search_emails(self, client, test_user_id):
        r = client.get("/emails/search", params={"q": "test", "user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "emails" in data
