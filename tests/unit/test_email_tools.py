"""Unit tests for email tools - full coverage for email account, read, send tools."""

from unittest.mock import patch


class TestEmailConnect:
    """Tests for email_connect tool."""

    def test_email_connect_requires_user_id(self):
        """Test email_connect requires user_id."""
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke({"email": "test@gmail.com", "password": "pass"})
        assert "Error: user_id is required" in result

    def test_email_connect_requires_email(self):
        """Test email_connect requires email."""
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke({"password": "pass", "user_id": "test_user"})
        assert "Error: email address is required" in result

    def test_email_connect_requires_password(self):
        """Test email_connect requires password."""
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke({"email": "test@gmail.com", "user_id": "test_user"})
        assert "Error: password is required" in result

    def test_email_connect_invalid_provider(self):
        """Test email_connect handles invalid provider."""
        from src.sdk.tools_core.email import email_connect

        result = email_connect.invoke(
            {"email": "invalid@unknown.com", "password": "pass", "user_id": "test_user"}
        )
        assert "Error: Could not detect email provider" in result


class TestEmailDisconnect:
    """Tests for email_disconnect tool."""

    def test_email_disconnect_requires_user_id(self):
        """Test email_disconnect requires user_id."""
        from src.sdk.tools_core.email import email_disconnect

        result = email_disconnect.invoke({"account_name": "test"})
        assert "Error" in result

    def test_email_disconnect_account_not_found(self):
        """Test email_disconnect handles non-existent account."""
        from src.sdk.tools_core.email import email_disconnect

        with patch("src.sdk.tools_core.email_db.load_accounts", return_value={}):
            result = email_disconnect.invoke(
                {"account_name": "nonexistent", "user_id": "test_user"}
            )
            assert "not found" in result


class TestEmailAccounts:
    """Tests for email_accounts tool."""

    def test_email_accounts_requires_user_id(self):
        """Test email_accounts requires user_id."""
        from src.sdk.tools_core.email import email_accounts

        result = email_accounts.invoke({})
        assert "Error" in result or "required" in result.lower()

    def test_email_accounts_empty(self):
        """Test email_accounts with no accounts."""
        from src.sdk.tools_core.email import email_accounts

        with patch("src.sdk.tools_core.email_db.load_accounts", return_value={}):
            result = email_accounts.invoke({"user_id": "test_user"})
            assert "No email accounts" in result or "not found" in result

    def test_email_accounts_list(self):
        """Test email_accounts lists connected accounts."""
        from src.sdk.tools_core.email import email_accounts

        mock_accounts = {
            "acc1": {
                "name": "Personal",
                "email": "test@gmail.com",
                "provider": "gmail",
                "status": "connected",
                "folders": ["INBOX"],
            }
        }
        with patch("src.sdk.tools_core.email_db.load_accounts", return_value=mock_accounts):
            result = email_accounts.invoke({"user_id": "test_user"})
            assert "Personal" in result
            assert "test@gmail.com" in result


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

        with patch("src.sdk.tools_core.email_db.get_account_id_by_name", return_value=None):
            result = email_list.invoke({"account_name": "nonexistent", "user_id": "test_user"})
            assert "not found" in result


class TestEmailGet:
    """Tests for email_get tool."""

    def test_email_get_requires_user_id(self):
        """Test email_get requires user_id."""
        from src.sdk.tools_core.email import email_get

        result = email_get.invoke({"email_id": "123", "account_name": "test"})
        assert "Error: user_id is required" in result

    def test_email_get_account_not_found(self):
        """Test email_get handles non-existent account."""
        from src.sdk.tools_core.email import email_get

        with patch("src.sdk.tools_core.email_db.get_account_id_by_name", return_value=None):
            result = email_get.invoke(
                {"email_id": "123", "account_name": "nonexistent", "user_id": "test_user"}
            )
            assert "not found" in result


class TestEmailSearch:
    """Tests for email_search tool."""

    def test_email_search_requires_user_id(self):
        """Test email_search requires user_id."""
        from src.sdk.tools_core.email import email_search

        result = email_search.invoke({"query": "test", "account_name": "test"})
        assert "Error: user_id is required" in result

    def test_email_search_requires_query(self):
        """Test email_search requires query."""
        from src.sdk.tools_core.email import email_search

        result = email_search.invoke({"account_name": "test", "user_id": "test_user"})
        assert "Error: query is required" in result

    def test_email_search_account_not_found(self):
        """Test email_search handles non-existent account."""
        from src.sdk.tools_core.email import email_search

        with patch("src.sdk.tools_core.email_db.get_account_id_by_name", return_value=None):
            result = email_search.invoke(
                {"query": "test", "account_name": "nonexistent", "user_id": "test_user"}
            )
            assert "not found" in result


class TestEmailSend:
    """Tests for email_send tool."""

    def test_email_send_requires_user_id(self):
        """Test email_send requires user_id."""
        from src.sdk.tools_core.email import email_send

        result = email_send.invoke(
            {"account_name": "test", "to": "test@example.com", "subject": "Hi", "body": "Hello"}
        )
        assert "Error: user_id is required" in result

    def test_email_send_reply_to_not_found(self):
        """Test email_send handles reply to non-existent email."""
        from src.sdk.tools_core.email import email_send

        with patch("src.sdk.tools_core.email_db.get_account_id_by_name", return_value=None):
            result = email_send.invoke(
                {
                    "account_name": "test",
                    "to": "test@example.com",
                    "subject": "Hi",
                    "body": "Hello",
                    "reply_to": "nonexistent",
                    "user_id": "test_user",
                }
            )
            assert "not found" in result
