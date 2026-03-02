"""Unit tests for email tools."""


class TestEmailAccountTools:
    """Tests for email account management tools."""

    def test_email_connect_with_invalid_provider(self):
        """Test email_connect handles invalid provider."""
        from src.tools.email.account import email_connect

        result = email_connect.invoke(
            {"email": "invalid@unknown.com", "password": "pass", "user_id": "test_user"}
        )
        assert "Error: Could not detect email provider" in result
