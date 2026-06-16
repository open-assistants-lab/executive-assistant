"""Unit tests for email tools."""

from unittest.mock import patch


class TestEmailConnect:
    """Tests for email_connect tool validation."""

    def test_requires_user_id(self):
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke({"email": "a@b.com", "password": "p"})
        assert "Error: user_id" in result

    def test_requires_email(self):
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke({"password": "p", "user_id": "u"})
        assert "Error: email" in result

    def test_requires_password(self):
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke({"email": "a@b.com", "user_id": "u"})
        assert "Error: password" in result


class TestEmailDisconnect:
    """Tests for email_disconnect tool."""

    def test_requires_user_id(self):
        from src.sdk.tools_core.email import email_disconnect

        result = email_disconnect.invoke({"account_name": "test"})
        assert "Error: user_id" in result

    def test_account_not_found(self):
        from src.sdk.tools_core.email import email_disconnect

        with patch("src.sdk.tools_core.email.get_account_id_by_name", return_value=None):
            result = email_disconnect.invoke({"account_name": "ghost", "user_id": "u"})
        assert "not found" in result


class TestEmailAccounts:
    """Tests for email_accounts tool."""

    def test_requires_user_id(self):
        from src.sdk.tools_core.email import email_accounts

        result = email_accounts.invoke({})
        assert "Error: user_id" in result

    def test_empty(self):
        from src.sdk.tools_core.email import email_accounts

        with patch("src.sdk.tools_core.email.load_accounts", return_value={}):
            result = email_accounts.invoke({"user_id": "u"})
        assert "No email accounts" in result


class TestEmailList:
    """Tests for email_list tool."""

    def test_email_list_requires_user_id(self):
        """Test email_list requires user_id."""
        from src.sdk.tools_core.email import email_list

        result = email_list.invoke({"account_name": "test"})
        assert "Error: user_id is required" in result

    def test_email_list_account_not_found(self):
        """Test email_list handles non-existent account."""
        from src.sdk.tools_core.email import email_list

        with patch("src.sdk.tools_core.email.get_account_id_by_name", return_value=None):
            result = email_list.invoke({"account_name": "ghost", "user_id": "test_user"})
        assert "not found" in result


class TestEmailGet:
    """Tests for email_get tool."""

    def test_email_get_requires_user_id(self):
        """Test email_get requires user_id."""
        from src.sdk.tools_core.email import email_get

        result = email_get.invoke({"email_id": "1", "account_name": "test"})
        assert "Error: user_id is required" in result


class TestEmailSearch:
    """Tests for email_search tool."""

    def test_email_search_requires_user_id(self):
        """Test email_search requires user_id."""
        from src.sdk.tools_core.email import email_search

        result = email_search.invoke({"query": "hello", "account_name": "test"})
        assert "Error: user_id is required" in result

    def test_email_search_requires_query(self):
        """Test email_search requires query."""
        from src.sdk.tools_core.email import email_search

        result = email_search.invoke({"account_name": "test", "user_id": "test_user"})
        assert "Error: query is required" in result


class TestEmailSend:
    """Tests for email_send tool."""

    def test_email_send_requires_user_id(self):
        """Test email_send requires user_id."""
        from src.sdk.tools_core.email import email_send

        result = email_send.invoke({"account_name": "test", "to": "a@b.com", "subject": "Hi", "body": "Hello"})
        assert "Error: user_id is required" in result
