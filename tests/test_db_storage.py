"""Tests for database storage (DuckDB-based tabular data)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cassey.storage.db_storage import (
    DBStorage,
    validate_identifier,
    sanitize_thread_id,
    get_db_storage,
)
from cassey.storage.file_sandbox import set_thread_id, clear_thread_id
from cassey.storage.group_storage import set_group_id, clear_group_id


# =============================================================================
# Identifier Validation Tests
# =============================================================================

class TestValidateIdentifier:
    """Test SQL identifier validation."""

    def test_valid_identifiers(self):
        """Test that valid identifiers pass validation."""
        assert validate_identifier("table_name") == "table_name"
        assert validate_identifier("_private") == "_private"
        assert validate_identifier("Table123") == "Table123"
        assert validate_identifier("camelCase") == "camelCase"

    def test_invalid_identifiers(self):
        """Test that invalid identifiers raise ValueError."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("123table")  # Starts with number

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("table-name")  # Contains hyphen

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("table name")  # Contains space

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("table.name")  # Contains dot

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("")  # Empty string

        # SQL injection attempt
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("users; DROP TABLE users--")


# =============================================================================
# Sanitize Thread ID Tests
# =============================================================================

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

    def test_sanitize_combined(self):
        """Test multiple special characters."""
        result = sanitize_thread_id("http:user:example@test/path")
        assert result == "http_user_example_test_path"


# =============================================================================
# DBStorage Tests
# =============================================================================

class TestDBStorage:
    """Test DBStorage class."""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create a temporary database root."""
        root = tmp_path / "db"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def storage(self, temp_root):
        """Create DBStorage instance with temp root."""
        return DBStorage(root=temp_root)

    def test_initialization(self, storage):
        """Test storage initialization."""
        assert storage.root.exists()
        assert storage.root.is_dir()

    def test_get_db_path_with_thread_id(self, storage, temp_root):
        """Test getting database path with thread_id."""
        db_path = storage._get_db_path(thread_id="test_thread")
        assert db_path.parent == temp_root
        assert db_path.suffix == ".db"

    def test_get_db_path_from_context(self, storage):
        """Test getting database path from context thread_id."""
        set_thread_id("test_thread")
        db_path = storage._get_db_path()
        assert "test_thread" in str(db_path)
        clear_thread_id()

    def test_get_db_path_error_no_context(self, storage):
        """Test error when no thread_id or workspace_id provided."""
        clear_thread_id()
        with pytest.raises(ValueError, match="No thread_id/workspace_id"):
            storage._get_db_path()

    def test_create_table_from_dict_data(self, storage):
        """Test creating table from list of dicts."""
        data = [
            {"name": "Alice", "age": 30, "active": True},
            {"name": "Bob", "age": 25, "active": False},
        ]

        storage.create_table_from_data("users", data, thread_id="test_thread")

        # Verify table exists
        tables = storage.list_tables(thread_id="test_thread")
        assert "users" in tables

        # Verify data
        results = storage.execute("SELECT * FROM users ORDER BY name", thread_id="test_thread")
        assert len(results) == 2
        assert results[0][0] == "Alice"
        assert results[0][1] == 30
        assert results[1][0] == "Bob"
        assert results[1][1] == 25

    def test_create_table_from_tuple_data(self, storage):
        """Test creating table from list of tuples."""
        data = [
            ("Apple", 1.99, 10),
            ("Banana", 0.99, 20),
        ]

        storage.create_table_from_data(
            "products",
            data,
            columns=["name", "price", "quantity"],
            thread_id="test_thread"
        )

        # Verify data
        results = storage.execute("SELECT * FROM products ORDER BY name", thread_id="test_thread")
        assert results[0][0] == "Apple"
        assert results[0][1] == 1.99

    def test_create_table_empty_data_with_columns(self, storage):
        """Test creating empty table with column definitions."""
        storage.create_table_from_data(
            "empty_table",
            [],
            columns=["id", "name", "email"],
            thread_id="test_thread"
        )

        # Verify table exists
        tables = storage.list_tables(thread_id="test_thread")
        assert "empty_table" in tables

        # Verify no data
        results = storage.execute("SELECT * FROM empty_table", thread_id="test_thread")
        assert len(results) == 0

    def test_create_table_error_no_data_no_columns(self, storage):
        """Test error when creating table without data or columns."""
        with pytest.raises(ValueError, match="Cannot create table"):
            storage.create_table_from_data("empty", [], thread_id="test_thread")

    def test_append_to_table(self, storage):
        """Test appending data to existing table."""
        # Create initial table
        initial_data = [{"name": "Alice", "age": 30}]
        storage.create_table_from_data("users", initial_data, thread_id="test_thread")

        # Append more data
        new_data = [{"name": "Bob", "age": 25}]
        storage.append_to_table("users", new_data, thread_id="test_thread")

        # Verify combined data
        results = storage.execute("SELECT * FROM users ORDER BY name", thread_id="test_thread")
        assert len(results) == 2

    def test_list_tables(self, storage):
        """Test listing all tables."""
        # Create multiple tables
        storage.create_table_from_data("table1", [{"a": 1}], thread_id="test_thread")
        storage.create_table_from_data("table2", [{"b": 2}], thread_id="test_thread")

        tables = storage.list_tables(thread_id="test_thread")
        assert "table1" in tables
        assert "table2" in tables

    def test_execute_query(self, storage):
        """Test executing SQL queries."""
        storage.create_table_from_data(
            "test",
            [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
            thread_id="test_thread"
        )

        # Simple query
        results = storage.execute("SELECT x FROM test WHERE y > 1", thread_id="test_thread")
        assert len(results) == 2
        assert results[0][0] == 1

        # Aggregation query
        results = storage.execute("SELECT SUM(x) FROM test", thread_id="test_thread")
        assert results[0][0] == 4

    def test_drop_table(self, storage):
        """Test dropping a table."""
        storage.create_table_from_data("temp", [{"a": 1}], thread_id="test_thread")

        # Drop and recreate
        storage.create_table_from_data("temp", [{"b": 2}], thread_id="test_thread")

        results = storage.execute("SELECT * FROM temp", thread_id="test_thread")
        assert len(results) == 1
        assert results[0][0] == 2

    def test_different_threads_isolated(self, storage):
        """Test that different threads have isolated databases."""
        # Create tables in different threads
        storage.create_table_from_data("table1", [{"value": 1}], thread_id="thread_1")
        storage.create_table_from_data("table2", [{"value": 2}], thread_id="thread_2")

        # Verify isolation
        tables_1 = storage.list_tables(thread_id="thread_1")
        tables_2 = storage.list_tables(thread_id="thread_2")

        assert "table1" in tables_1
        assert "table2" not in tables_1

        assert "table2" in tables_2
        assert "table1" not in tables_2


# =============================================================================
# get_db_storage Tests
# =============================================================================

class TestGetDBStorage:
    """Test get_db_storage singleton function."""

    def test_get_db_storage_returns_singleton(self, tmp_path):
        """Test that get_db_storage returns the same instance."""
        with patch("cassey.storage.db_storage.settings.DB_ROOT", tmp_path / "db"):
            storage1 = get_db_storage()
            storage2 = get_db_storage()
            assert storage1 is storage2



# =============================================================================
# Integration Tests with Context
# =============================================================================

class TestDBStorageWithContext:
    """Test DBStorage with context variables."""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create a temporary database root."""
        root = tmp_path / "db"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def storage(self, temp_root):
        """Create DBStorage instance."""
        return DBStorage(root=temp_root)

    def test_uses_thread_id_from_context(self, storage):
        """Test that thread_id from context is used."""
        set_thread_id("context_thread")

        storage.create_table_from_data("test", [{"a": 1}])

        tables = storage.list_tables()
        assert "test" in tables

        # Verify DB file is in the right location
        db_path = storage._get_db_path()
        assert "context_thread" in str(db_path)

        clear_thread_id()


# =============================================================================
# Real Data Tests
# =============================================================================

class TestDBStorageWithRealData:
    """Test DBStorage with realistic data scenarios."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create DBStorage for testing."""
        root = tmp_path / "db"
        root.mkdir(parents=True, exist_ok=True)
        return DBStorage(root=root)

    def test_crud_operations(self, storage):
        """Test complete CRUD cycle."""
        thread_id = "test_thread"

        # Create
        storage.create_table_from_data(
            "tasks",
            [
                {"id": 1, "title": "Task 1", "status": "pending"},
                {"id": 2, "title": "Task 2", "status": "done"},
            ],
            thread_id=thread_id
        )

        # Read
        results = storage.execute("SELECT * FROM tasks WHERE status = 'pending'", thread_id=thread_id)
        assert len(results) == 1
        assert results[0][1] == "Task 1"

        # Update (via drop and recreate)
        storage.create_table_from_data(
            "tasks",
            [
                {"id": 1, "title": "Task 1 Updated", "status": "in_progress"},
                {"id": 2, "title": "Task 2", "status": "done"},
            ],
            thread_id=thread_id
        )

        results = storage.execute("SELECT title FROM tasks WHERE id = 1", thread_id=thread_id)
        assert results[0][0] == "Task 1 Updated"

    def test_complex_query(self, storage):
        """Test complex SQL queries."""
        thread_id = "test_thread"

        # Create sales data
        storage.create_table_from_data(
            "sales",
            [
                {"product": "A", "region": "North", "amount": 100},
                {"product": "A", "region": "South", "amount": 200},
                {"product": "B", "region": "North", "amount": 150},
                {"product": "B", "region": "South", "amount": 250},
            ],
            thread_id=thread_id
        )

        # Group by query
        results = storage.execute(
            "SELECT product, SUM(amount) as total FROM sales GROUP BY product ORDER BY product",
            thread_id=thread_id
        )
        assert len(results) == 2
        assert results[0][1] == 300  # Product A total
        assert results[1][1] == 400  # Product B total

    def test_joins(self, storage):
        """Test JOIN operations."""
        thread_id = "test_thread"

        storage.create_table_from_data(
            "users",
            [
                {"id": 1, "name": "Alice", "dept_id": 101},
                {"id": 2, "name": "Bob", "dept_id": 102},
            ],
            thread_id=thread_id
        )

        storage.create_table_from_data(
            "departments",
            [
                {"dept_id": 101, "dept_name": "Engineering"},
                {"dept_id": 102, "dept_name": "Sales"},
            ],
            thread_id=thread_id
        )

        # Join query
        results = storage.execute(
            """SELECT u.name, d.dept_name
               FROM users u
               JOIN departments d ON u.dept_id = d.dept_id
               ORDER BY u.name""",
            thread_id=thread_id
        )

        assert len(results) == 2
        assert results[0][0] == "Alice"
        assert results[0][1] == "Engineering"
