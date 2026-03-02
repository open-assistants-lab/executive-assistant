"""Unit tests for contacts tools."""

import pytest


class TestContactsStorageFunctions:
    """Tests for contacts storage functions."""

    def test_get_db_path(self):
        """Test getting database path."""
        from src.tools.contacts.storage import get_db_path

        path = get_db_path("test_user")
        assert "test_user" in path
        assert "contacts.db" in path

    def test_get_db_path_invalid_user(self):
        """Test get_db_path rejects invalid user."""
        from src.tools.contacts.storage import get_db_path

        with pytest.raises(ValueError):
            get_db_path("default")

    def test_get_db_path_empty_user(self):
        """Test get_db_path rejects empty user."""
        from src.tools.contacts.storage import get_db_path

        with pytest.raises(ValueError):
            get_db_path("")
