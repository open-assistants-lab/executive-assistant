"""Unit tests for background services (email sync)."""

from unittest.mock import patch

import pytest


class TestEmailSync:
    """Tests for email sync background service."""

    @pytest.mark.asyncio
    async def test_sync_all_accounts_empty(self):
        """Test syncing with no accounts."""
        from src.sdk.tools_core.email_sync import _sync_all_accounts

        with patch("src.sdk.tools_core.email_sync._load_accounts") as mock_load:
            with patch("src.sdk.tools_core.email_sync._sync_emails") as mock_sync:
                mock_load.return_value = {}

                await _sync_all_accounts()

                mock_sync.assert_not_called()


class TestEmailSyncConfig:
    """Tests for email sync configuration."""

    def test_email_sync_config(self):
        """Test email sync config loads correctly."""
        from src.config.settings import get_settings

        settings = get_settings()
        assert hasattr(settings, "email_sync")


class TestEmailSyncRateLimiting:
    """Tests for email sync rate limiting."""

    def test_rate_limit_cooldown_init(self):
        """Test rate limit cooldown dict is initialized."""
        from src.sdk.tools_core.email_sync import RATE_LIMIT_COOLDOWN

        assert isinstance(RATE_LIMIT_COOLDOWN, dict)
