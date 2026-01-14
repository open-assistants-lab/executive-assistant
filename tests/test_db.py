"""Unit tests for database storage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cassey.storage.db_storage import DBStorage, get_db_storage, sanitize_thread_id


@pytest.fixture
def temp_db_root(tmp_path):
    """Create a temporary database root for testing."""
    return tmp_path / "db"


@pytest.fixture
def db_store(temp_db_root):
    """Create a database storage instance with temporary root."""
    return DBStorage(root=temp_db_root)


class TestSanitizeThreadId:
    """Test thread_id sanitization for database filenames."""

    def test_sanitize_colons(self):
        """Test that colons are replaced."""
        assert sanitize_thread_id("telegram:user123") == "telegram_user123"

    def test_sanitize_slashes(self):
        """Test that slashes are replaced."""
        assert sanitize_thread_id("user/with/slash") == "user_with_slash"

    def test_sanitize_at_sign(self):
        """Test that @ signs are replaced."""
        assert sanitize_thread_id("email:user@example.com") == "email_user_example.com"

    def test_sanitize_backslashes(self):
        """Test that backslashes are replaced."""
        assert sanitize_thread_id(r"user\with\backslash") == "user_with_backslash"

    def test_sanitize_combined(self):
        """Test multiple special characters."""
        assert (
            sanitize_thread_id("http:user:example@test/path")
            == "http_user_example_test_path"
        )


class TestDBStorage:
    """Test database storage operations."""

    def test_initialization(self, db_store):
        """Test storage initialization."""
        assert db_store.root.exists()
        assert db_store.root.is_dir()

    def test_get_db_path(self, db_store):
        """Test getting database path for thread."""
        db_path = db_store._get_db_path("telegram:test123")
        assert db_path.name == "telegram_test123.db"
        assert db_path.parent == db_store.root

    def test_get_db_path_sanitizes(self, db_store):
        """Test that thread_id is sanitized in db path."""
        db_path = db_store._get_db_path("email:user@test.com")
        assert db_path.name == "email_user_test.com.db"

    def test_get_db_path_no_thread_id_raises(self, db_store):
        """Test that get_db_path raises when no thread_id."""
        with patch("cassey.storage.db_storage.get_thread_id", return_value=None):
            with pytest.raises(ValueError, match="No thread_id"):
                db_store._get_db_path()

    def test_create_table_from_dict(self, db_store):
        """Test creating table from list of dicts."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]

        db_store.create_table_from_data("users", data, None, "test_thread")

        # Verify table exists
        tables = db_store.list_tables("test_thread")
        assert "users" in tables

        # Verify data
        result = db_store.execute("SELECT * FROM users", "test_thread")
        assert len(result) == 2
        assert result[0][0] == "Alice"

    def test_create_table_from_tuples(self, db_store):
        """Test creating table from list of tuples."""
        data = [
            ("Apple", 1.99),
            ("Banana", 0.99),
        ]

        db_store.create_table_from_data(
            "products", data, ["name", "price"], "test_thread"
        )

        # Verify table exists
        tables = db_store.list_tables("test_thread")
        assert "products" in tables

    def test_create_table_replaces_existing(self, db_store):
        """Test that creating table replaces existing one."""
        data1 = [{"name": "Alice"}]
        data2 = [{"name": "Bob"}]

        db_store.create_table_from_data("users", data1, None, "test_thread")
        db_store.create_table_from_data("users", data2, None, "test_thread")

        result = db_store.execute("SELECT * FROM users", "test_thread")
        assert len(result) == 1
        assert result[0][0] == "Bob"

    def test_append_to_table(self, db_store):
        """Test appending data to existing table."""
        initial_data = [{"name": "Alice", "age": 30}]
        new_data = [{"name": "Bob", "age": 25}]

        db_store.create_table_from_data("users", initial_data, None, "test_thread")
        db_store.append_to_table("users", new_data, "test_thread")

        result = db_store.execute("SELECT * FROM users ORDER BY name", "test_thread")
        assert len(result) == 2
        assert result[0][0] == "Alice"
        assert result[1][0] == "Bob"

    def test_list_tables(self, db_store):
        """Test listing all tables."""
        # Create some tables
        db_store.create_table_from_data("table1", [{"a": 1}], None, "test_thread")
        db_store.create_table_from_data("table2", [{"b": 2}], None, "test_thread")

        tables = db_store.list_tables("test_thread")
        assert set(tables) == {"table1", "table2"}

    def test_list_tables_empty(self, db_store):
        """Test listing tables when database is empty."""
        tables = db_store.list_tables("test_thread")
        assert tables == []

    def test_table_exists(self, db_store):
        """Test checking if table exists."""
        assert not db_store.table_exists("users", "test_thread")

        db_store.create_table_from_data("users", [{"a": 1}], None, "test_thread")

        assert db_store.table_exists("users", "test_thread")

    def test_drop_table(self, db_store):
        """Test dropping a table."""
        db_store.create_table_from_data("temp", [{"a": 1}], None, "test_thread")

        assert db_store.table_exists("temp", "test_thread")

        db_store.drop_table("temp", "test_thread")

        assert not db_store.table_exists("temp", "test_thread")

    def test_drop_table_nonexistent(self, db_store):
        """Test dropping non-existent table doesn't error."""
        # Should not raise
        db_store.drop_table("nonexistent", "test_thread")

    def test_get_table_info(self, db_store):
        """Test getting table schema info."""
        data = [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False},
        ]

        db_store.create_table_from_data("users", data, None, "test_thread")

        info = db_store.get_table_info("users", "test_thread")

        assert len(info) == 3
        column_names = {col["name"] for col in info}
        assert "id" in column_names
        assert "name" in column_names
        assert "active" in column_names

    def test_delete_db(self, db_store):
        """Test deleting a database file."""
        # Create a database by creating a table
        db_store.create_table_from_data("test", [{"a": 1}], None, "delete_thread")
        db_path = db_store._get_db_path("delete_thread")

        assert db_path.exists()

        result = db_store.delete_db("delete_thread")

        assert result is True
        assert not db_path.exists()

    def test_delete_db_nonexistent(self, db_store):
        """Test deleting non-existent database returns False."""
        result = db_store.delete_db("nonexistent_thread")
        assert result is False

    def test_execute_query(self, db_store):
        """Test executing SQL query."""
        data = [
            {"name": "Alice", "score": 100},
            {"name": "Bob", "score": 85},
        ]

        db_store.create_table_from_data("scores", data, None, "test_thread")

        result = db_store.execute(
            "SELECT name FROM scores WHERE score > 90", "test_thread"
        )

        assert len(result) == 1
        assert result[0][0] == "Alice"

    def test_execute_query_empty_result(self, db_store):
        """Test executing query that returns no results."""
        db_store.create_table_from_data("test", [{"a": 1}], None, "test_thread")

        result = db_store.execute("SELECT * FROM test WHERE a > 100", "test_thread")

        assert result == []

    def test_execute_df(self, db_store):
        """Test executing query that returns DataFrame."""
        data = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]

        db_store.create_table_from_data("data", data, None, "test_thread")

        df = db_store.execute_df("SELECT * FROM data", "test_thread")

        assert len(df) == 2
        assert list(df.columns) == ["x", "y"]

    def test_thread_isolation(self, db_store):
        """Test that different threads have isolated databases."""
        # Create table in thread1
        db_store.create_table_from_data(
            "table1", [{"a": 1}], None, "thread1"
        )

        # Create table in thread2
        db_store.create_table_from_data(
            "table2", [{"b": 2}], None, "thread2"
        )

        # Thread1 should only see its own table
        tables1 = db_store.list_tables("thread1")
        assert tables1 == ["table1"]

        # Thread2 should only see its own table
        tables2 = db_store.list_tables("thread2")
        assert tables2 == ["table2"]


class TestGlobalDBStorage:
    """Test global database storage instance."""

    def test_get_db_storage(self):
        """Test getting global storage instance."""
        storage = get_db_storage()
        assert isinstance(storage, DBStorage)

    def test_global_instance_singleton(self):
        """Test that global instance is a singleton."""
        storage1 = get_db_storage()
        storage2 = get_db_storage()
        assert storage1 is storage2
