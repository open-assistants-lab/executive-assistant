"""Unit tests for contacts tools - full coverage for all CRUD operations."""

from unittest.mock import patch

import pytest

TEST_USER_ID = "test_contacts_user"

_MOCK = "src.sdk.tools_core.contacts"


class TestContactsList:
    """Tests for contacts_list tool."""

    def test_contacts_list_requires_user_id(self):
        """Test contacts_list requires user_id."""
        from src.sdk.tools_core.contacts import contacts_list

        result = contacts_list.invoke({})
        assert "Error: user_id is required" in result

    def test_contacts_list_empty(self):
        """Test contacts_list with no contacts."""
        from src.sdk.tools_core.contacts import contacts_list

        with patch(f"{_MOCK}.get_contacts", return_value=[]):
            with patch(f"{_MOCK}.get_contacts_count", return_value=0):
                result = contacts_list.invoke({"user_id": TEST_USER_ID})
                assert "No contacts" in result

    def test_contacts_list_with_contacts(self):
        """Test contacts_list returns contacts."""
        from src.sdk.tools_core.contacts import contacts_list

        mock_contacts = [
            {
                "name": "John Doe",
                "email": "john@example.com",
                "company": "Acme",
                "phone": "555-1234",
            }
        ]
        with patch(f"{_MOCK}.get_contacts", return_value=mock_contacts):
            with patch(f"{_MOCK}.get_contacts_count", return_value=1):
                result = contacts_list.invoke({"user_id": TEST_USER_ID})
                assert "John Doe" in result
                assert "john@example.com" in result


class TestContactsGet:
    """Tests for contacts_get tool."""

    def test_contacts_get_requires_user_id(self):
        """Test contacts_get requires user_id."""
        from src.sdk.tools_core.contacts import contacts_get

        result = contacts_get.invoke({})
        assert "Error: user_id is required" in result

    def test_contacts_get_requires_email_or_id(self):
        """Test contacts_get requires email or contact_id."""
        from src.sdk.tools_core.contacts import contacts_get

        result = contacts_get.invoke({"user_id": TEST_USER_ID})
        assert "Error: email or contact_id is required" in result

    def test_contacts_get_not_found(self):
        """Test contacts_get when contact not found."""
        from src.sdk.tools_core.contacts import contacts_get

        with patch(f"{_MOCK}.storage_get_contact", return_value=None):
            result = contacts_get.invoke({"email": "notfound@example.com", "user_id": TEST_USER_ID})
            assert "not found" in result

    def test_contacts_get_found(self):
        """Test contacts_get returns contact details."""
        from src.sdk.tools_core.contacts import contacts_get

        mock_contact = {
            "id": "123",
            "name": "Jane Doe",
            "email": "jane@example.com",
            "company": "Tech Corp",
            "phone": "555-5678",
            "source": "email",
        }
        with patch(f"{_MOCK}.storage_get_contact", return_value=mock_contact):
            result = contacts_get.invoke({"email": "jane@example.com", "user_id": TEST_USER_ID})
            assert "Jane Doe" in result
            assert "jane@example.com" in result
            assert "Tech Corp" in result


class TestContactsAdd:
    """Tests for contacts_add tool."""

    def test_contacts_add_requires_user_id(self):
        """Test contacts_add requires user_id."""
        from src.sdk.tools_core.contacts import contacts_add

        result = contacts_add.invoke({"email": "test@example.com"})
        assert "Error: user_id is required" in result

    def test_contacts_add_requires_email(self):
        """Test contacts_add requires email - Pydantic validates this before function code."""
        from src.sdk.tools_core.contacts import contacts_add

        with pytest.raises(Exception) as exc_info:
            contacts_add.invoke({"user_id": TEST_USER_ID})
        assert "Field required" in str(exc_info.value) or "email" in str(exc_info.value).lower()

    def test_contacts_add_success(self):
        """Test contacts_add successfully adds contact."""
        from src.sdk.tools_core.contacts import contacts_add

        with patch(
            f"{_MOCK}.storage_add_contact",
            return_value={"success": True, "id": "new123"},
        ):
            result = contacts_add.invoke(
                {
                    "email": "new@example.com",
                    "name": "New Contact",
                    "phone": "555-0000",
                    "company": "NewCo",
                    "user_id": TEST_USER_ID,
                }
            )
            assert "added" in result.lower() or "success" in result.lower()

    def test_contacts_add_failure(self):
        """Test contacts_add handles failure."""
        from src.sdk.tools_core.contacts import contacts_add

        with patch(
            f"{_MOCK}.storage_add_contact",
            return_value={"success": False, "error": "Duplicate email"},
        ):
            result = contacts_add.invoke({"email": "existing@example.com", "user_id": TEST_USER_ID})
            assert "Error" in result or "Duplicate" in result


class TestContactsUpdate:
    """Tests for contacts_update tool."""

    def test_contacts_update_requires_user_id(self):
        """Test contacts_update requires user_id."""
        from src.sdk.tools_core.contacts import contacts_update

        result = contacts_update.invoke({})
        assert "Error: user_id is required" in result

    def test_contacts_update_requires_email_or_id(self):
        """Test contacts_update requires email or contact_id."""
        from src.sdk.tools_core.contacts import contacts_update

        result = contacts_update.invoke({"user_id": TEST_USER_ID})
        assert "Error: email or contact_id is required" in result

    def test_contacts_update_success(self):
        """Test contacts_update successfully updates contact."""
        from src.sdk.tools_core.contacts import contacts_update

        with patch(
            f"{_MOCK}.storage_update_contact",
            return_value={"success": True},
        ):
            result = contacts_update.invoke(
                {"email": "test@example.com", "name": "Updated Name", "user_id": TEST_USER_ID}
            )
            assert "updated" in result.lower() or "success" in result.lower()

    def test_contacts_update_failure(self):
        """Test contacts_update handles failure."""
        from src.sdk.tools_core.contacts import contacts_update

        with patch(
            f"{_MOCK}.storage_update_contact",
            return_value={"success": False, "error": "Not found"},
        ):
            result = contacts_update.invoke(
                {"email": "notfound@example.com", "user_id": TEST_USER_ID}
            )
            assert "Error" in result


class TestContactsDelete:
    """Tests for contacts_delete tool."""

    def test_contacts_delete_requires_user_id(self):
        """Test contacts_delete requires user_id."""
        from src.sdk.tools_core.contacts import contacts_delete

        result = contacts_delete.invoke({})
        assert "Error: user_id is required" in result

    def test_contacts_delete_requires_email_or_id(self):
        """Test contacts_delete requires email or contact_id."""
        from src.sdk.tools_core.contacts import contacts_delete

        result = contacts_delete.invoke({"user_id": TEST_USER_ID})
        assert "Error: email or contact_id is required" in result

    def test_contacts_delete_success(self):
        """Test contacts_delete successfully deletes contact."""
        from src.sdk.tools_core.contacts import contacts_delete

        with patch(
            f"{_MOCK}.storage_delete_contact",
            return_value={"success": True},
        ):
            result = contacts_delete.invoke(
                {"email": "delete@example.com", "user_id": TEST_USER_ID}
            )
            assert "deleted" in result.lower() or "success" in result.lower()

    def test_contacts_delete_failure(self):
        """Test contacts_delete handles failure."""
        from src.sdk.tools_core.contacts import contacts_delete

        with patch(
            f"{_MOCK}.storage_delete_contact",
            return_value={"success": False, "error": "Not found"},
        ):
            result = contacts_delete.invoke(
                {"email": "notfound@example.com", "user_id": TEST_USER_ID}
            )
            assert "Error" in result


class TestContactsSearch:
    """Tests for contacts_search tool."""

    def test_contacts_search_requires_user_id(self):
        """Test contacts_search requires user_id."""
        from src.sdk.tools_core.contacts import contacts_search

        result = contacts_search.invoke({"query": "test"})
        assert "Error: user_id is required" in result

    def test_contacts_search_requires_query(self):
        """Test contacts_search requires query - Pydantic validates this before function code."""
        from src.sdk.tools_core.contacts import contacts_search

        with pytest.raises(Exception) as exc_info:
            contacts_search.invoke({"user_id": TEST_USER_ID})
        assert "Field required" in str(exc_info.value) or "query" in str(exc_info.value).lower()

    def test_contacts_search_empty(self):
        """Test contacts_search with no results."""
        from src.sdk.tools_core.contacts import contacts_search

        with patch(f"{_MOCK}.search_contacts", return_value=[]):
            result = contacts_search.invoke({"query": "nonexistent", "user_id": TEST_USER_ID})
            assert "No contacts found" in result

    def test_contacts_search_results(self):
        """Test contacts_search returns results."""
        from src.sdk.tools_core.contacts import contacts_search

        mock_results = [{"name": "John Smith", "email": "john@company.com", "company": "Tech Inc"}]
        with patch(f"{_MOCK}.search_contacts", return_value=mock_results):
            result = contacts_search.invoke({"query": "John", "user_id": TEST_USER_ID})
            assert "John Smith" in result
            assert "john@company.com" in result


class TestContactsStorageFunctions:
    """Tests for contacts storage functions."""

    def test_get_db_path(self):
        """Test getting database path."""
        from src.sdk.tools_core.contacts_storage import get_db_path

        path = get_db_path("test_user")
        assert "test_user" in path
        assert "contacts.db" in path

    def test_get_db_path_invalid_user(self):
        """Test get_db_path rejects invalid user."""
        from src.sdk.tools_core.contacts_storage import get_db_path

        with pytest.raises(ValueError):
            get_db_path("default")

    def test_get_db_path_empty_user(self):
        """Test get_db_path rejects empty user."""
        from src.sdk.tools_core.contacts_storage import get_db_path

        with pytest.raises(ValueError):
            get_db_path("")
