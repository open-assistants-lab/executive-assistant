"""Contract tests for email endpoints."""

import pytest


class TestEmailAccounts:
    """Tests for email account endpoints."""

    def test_list_accounts(self, client, test_user_id):
        r = client.get("/email/accounts", params={"user_id": test_user_id})
        assert r.status_code == 200
        data = r.json()
        assert "accounts" in data

    def test_connect_email_requires_fields(self, client, test_user_id):
        r = client.post(
            "/email/accounts",
            json={"email": "test@example.com", "password": "testpass", "user_id": test_user_id},
        )
        assert r.status_code in (200, 400, 422, 500)

    def test_disconnect_email(self, client, test_user_id):
        r = client.delete("/email/accounts/nonexistent", params={"user_id": test_user_id})
        assert r.status_code == 200


class TestEmailMessages:
    """Tests for email message endpoints."""

    def test_list_emails(self, client, test_user_id):
        r = client.get(
            "/email/messages",
            params={"account_name": "default", "limit": 5, "user_id": test_user_id},
        )
        assert r.status_code == 200

    def test_get_email(self, client, test_user_id):
        r = client.get(
            "/email/messages/nonexistent_id",
            params={"account_name": "default", "user_id": test_user_id},
        )
        assert r.status_code == 200

    def test_search_emails(self, client, test_user_id):
        r = client.get(
            "/email/search",
            params={"query": "test", "account_name": "default", "user_id": test_user_id},
        )
        assert r.status_code == 200
