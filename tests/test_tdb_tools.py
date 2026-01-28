"""Comprehensive tests for TDB (Transactional Database) tools.

This test suite covers all 10 TDB tools:
1. create_tdb_table
2. insert_tdb_table
3. query_tdb
4. list_tdb_tables
5. describe_tdb_table
6. export_tdb_table
7. import_tdb_table
8. add_tdb_column
9. drop_tdb_column
10. delete_tdb_table
"""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from executive_assistant.storage.thread_storage import set_thread_id, get_thread_tdb_path

# Import from the tool registry to get unwrapped functions
from executive_assistant.tools.registry import get_tdb_tools

# Get tools and extract their underlying functions
async def _get_tdb_functions():
    tools = await get_tdb_tools()
    tool_map = {t.name: t for t in tools}

    return {
        'create_tdb_table': tool_map['create_tdb_table'].func if hasattr(tool_map['create_tdb_table'], 'func') else tool_map['create_tdb_table'],
        'insert_tdb_table': tool_map['insert_tdb_table'].func if hasattr(tool_map['insert_tdb_table'], 'func') else tool_map['insert_tdb_table'],
        'query_tdb': tool_map['query_tdb'].func if hasattr(tool_map['query_tdb'], 'func') else tool_map['query_tdb'],
        'list_tdb_tables': tool_map['list_tdb_tables'].func if hasattr(tool_map['list_tdb_tables'], 'func') else tool_map['list_tdb_tables'],
        'describe_tdb_table': tool_map['describe_tdb_table'].func if hasattr(tool_map['describe_tdb_table'], 'func') else tool_map['describe_tdb_table'],
        'delete_tdb_table': tool_map['delete_tdb_table'].func if hasattr(tool_map['delete_tdb_table'], 'func') else tool_map['delete_tdb_table'],
        'export_tdb_table': tool_map['export_tdb_table'].func if hasattr(tool_map['export_tdb_table'], 'func') else tool_map['export_tdb_table'],
        'import_tdb_table': tool_map['import_tdb_table'].func if hasattr(tool_map['import_tdb_table'], 'func') else tool_map['import_tdb_table'],
        'add_tdb_column': tool_map['add_tdb_column'].func if hasattr(tool_map['add_tdb_column'], 'func') else tool_map['add_tdb_column'],
        'drop_tdb_column': tool_map['drop_tdb_column'].func if hasattr(tool_map['drop_tdb_column'], 'func') else tool_map['drop_tdb_column'],
    }

# Simple workaround: just run basic smoke test to verify tools exist


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_thread_id() -> str:
    """Provide a test thread ID for isolated storage."""
    return "test_tdb_tools"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    """Set up thread context for TDB operations."""
    # Set thread_id ContextVar
    set_thread_id(test_thread_id)
    yield
    # Cleanup happens automatically via test isolation


@pytest.fixture
def sample_data() -> list[dict]:
    """Provide sample employee data."""
    return [
        {"id": 1, "name": "Alice", "department": "Engineering", "salary": 95000},
        {"id": 2, "name": "Bob", "department": "Sales", "salary": 87000},
        {"id": 3, "name": "Charlie", "department": "Engineering", "salary": 105000},
    ]


@pytest.fixture
def sample_csv_file() -> Generator[Path, None, None]:
    """Create a temporary CSV file for import/export tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("id,name,department,department\n")
        f.write("4,Diana,Marketing,92000\n")
        f.write("5,Eve,Engineering,98000\n")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


# =============================================================================
# Test: create_tdb_table
# =============================================================================

class TestCreateTDBTable:
    """Tests for create_tdb_table tool."""

    def test_create_table_from_list(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test creating a table from a list of dictionaries."""
        result = create_tdb_table(
            table_name="employees",
            data=sample_data,
            scope="context"
        )

        assert "created" in result.lower()
        assert "3 rows" in result.lower()

        # Verify table exists
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_create_table_infer_schema(
        self, setup_thread_context: None
    ) -> None:
        """Test that table schema is inferred from data."""
        data = [{"id": 1, "name": "Test", "active": True}]

        create_tdb_table(table_name="test_table", data=data, scope="context")

        # Verify schema
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(test_table)")
        columns = [row[1] for row in cursor.fetchall()]

        assert "id" in columns
        assert "name" in columns
        assert "active" in columns
        conn.close()


# =============================================================================
# Test: insert_tdb_table
# =============================================================================

class TestInsertTDBTable:
    """Tests for insert_tdb_table tool."""

    def test_insert_into_existing_table(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test inserting data into an existing table."""
        # Create table first
        create_tdb_table(table_name="employees", data=sample_data[:2], scope="context")

        # Insert more data
        new_data = [{"id": 3, "name": "Charlie", "department": "Engineering", "salary": 105000}]
        result = insert_tdb_table(table_name="employees", data=new_data, scope="context")

        assert "inserted" in result.lower()
        assert "1 row" in result.lower()

        # Verify data
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        assert count == 3
        conn.close()


# =============================================================================
# Test: query_tdb
# =============================================================================

class TestQueryTDB:
    """Tests for query_tdb tool."""

    def test_query_all_rows(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test querying all rows from a table."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        result = query_tdb(sql="SELECT * FROM employees", scope="context")

        assert "3 rows" in result.lower() or "alice" in result.lower()

    def test_query_with_where_clause(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test querying with a WHERE clause."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        result = query_tdb(
            sql="SELECT * FROM employees WHERE department = 'Engineering'",
            scope="context"
        )

        assert "alice" in result.lower()
        assert "charlie" in result.lower()
        assert "bob" not in result.lower()  # Bob is in Sales


# =============================================================================
# Test: list_tdb_tables
# =============================================================================

class TestListTDBTables:
    """Tests for list_tdb_tables tool."""

    def test_list_empty_database(self, setup_thread_context: None) -> None:
        """Test listing tables when database is empty."""
        result = list_tdb_tables(scope="context")

        assert "no tables" in result.lower() or "empty" in result.lower()

    def test_list_multiple_tables(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test listing multiple tables."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")
        create_tdb_table(
            table_name="departments",
            data=[{"id": 1, "name": "Engineering"}],
            scope="context"
        )

        result = list_tdb_tables(scope="context")

        assert "employees" in result.lower()
        assert "departments" in result.lower()


# =============================================================================
# Test: describe_tdb_table
# =============================================================================

class TestDescribeTDBTable:
    """Tests for describe_tdb_table tool."""

    def test_describe_table_schema(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test describing table schema."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        result = describe_tdb_table(table_name="employees", scope="context")

        assert "employees" in result.lower()
        assert "schema" in result.lower()
        assert "id" in result.lower()
        assert "name" in result.lower()
        assert "department" in result.lower()


# =============================================================================
# Test: export_tdb_table
# =============================================================================

class TestExportTDBTable:
    """Tests for export_tdb_table tool."""

    def test_export_to_csv(
        self,
        setup_thread_context: None,
        sample_data: list[dict],
        tmp_path: Path
    ) -> None:
        """Test exporting table to CSV."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        export_path = tmp_path / "employees_export.csv"
        result = export_tdb_table(
            table_name="employees",
            filename=str(export_path),
            format="csv",
            scope="context"
        )

        assert "exported" in result.lower()
        assert export_path.exists()

        # Verify CSV content
        content = export_path.read_text()
        assert "Alice" in content
        assert "Bob" in content


# =============================================================================
# Test: import_tdb_table
# =============================================================================

class TestImportTDBTable:
    """Tests for import_tdb_table tool."""

    def test_import_from_csv(
        self,
        setup_thread_context: None,
        sample_data: list[dict],
        sample_csv_file: Path
    ) -> None:
        """Test importing data from CSV into existing table."""
        # Create table first
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        # Import from CSV
        result = import_tdb_table(
            table_name="employees",
            filename=str(sample_csv_file),
            scope="context"
        )

        assert "imported" in result.lower() or "rows" in result.lower()

        # Verify new data was added
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        assert count == 5  # 3 original + 2 imported
        conn.close()


# =============================================================================
# Test: add_tdb_column
# =============================================================================

class TestAddTDBColumn:
    """Tests for add_tdb_column tool."""

    def test_add_column_to_table(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test adding a new column to an existing table."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        result = add_tdb_column(
            table_name="employees",
            column_name="hire_date",
            column_type="TEXT",
            scope="context"
        )

        assert "added" in result.lower() or "column" in result.lower()

        # Verify column exists
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "hire_date" in columns
        conn.close()


# =============================================================================
# Test: drop_tdb_column
# =============================================================================

class TestDropTDBColumn:
    """Tests for drop_tdb_column tool."""

    def test_drop_column_from_table(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test dropping a column from an existing table."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        result = drop_tdb_column(
            table_name="employees",
            column_name="salary",
            scope="context"
        )

        assert "dropped" in result.lower() or "column" in result.lower()

        # Verify column is gone
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "salary" not in columns
        conn.close()


# =============================================================================
# Test: delete_tdb_table
# =============================================================================

class TestDeleteTDBTable:
    """Tests for delete_tdb_table tool."""

    def test_delete_existing_table(
        self, setup_thread_context: None, sample_data: list[dict]
    ) -> None:
        """Test deleting an existing table."""
        create_tdb_table(table_name="employees", data=sample_data, scope="context")

        result = delete_tdb_table(table_name="employees", scope="context")

        assert "dropped" in result.lower() or "deleted" in result.lower()

        # Verify table is gone
        db_path = get_thread_tdb_path("test_tdb_tools")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
        assert cursor.fetchone() is None
        conn.close()


# =============================================================================
# Integration Tests: Multi-Step Workflows
# =============================================================================

class TestTDBWorkflows:
    """Integration tests for common TDB workflows."""

    def test_full_lifecycle_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test complete table lifecycle: create, insert, query, modify, delete."""
        # 1. Create table
        data = [
            {"id": 1, "name": "Alice", "score": 95},
            {"id": 2, "name": "Bob", "score": 87}
        ]
        create_tdb_table(table_name="students", data=data, scope="context")

        # 2. Insert more data
        new_data = [{"id": 3, "name": "Charlie", "score": 92}]
        insert_tdb_table(table_name="students", data=new_data, scope="context")

        # 3. Query with filter
        result = query_tdb(
            sql="SELECT * FROM students WHERE score >= 90",
            scope="context"
        )
        assert "Alice" in result
        assert "Charlie" in result
        assert "Bob" not in result

        # 4. Add column
        add_tdb_column(
            table_name="students",
            column_name="grade",
            column_type="TEXT",
            scope="context"
        )

        # 5. Drop column
        drop_tdb_column(table_name="students", column_name="score", scope="context")

        # 6. Verify schema changed
        schema_result = describe_tdb_table(table_name="students", scope="context")
        assert "grade" in schema_result.lower()
        assert "score" not in schema_result.lower()

        # 7. Delete table
        delete_tdb_table(table_name="students", scope="context")

        # 8. Verify deletion
        tables = list_tdb_tables(scope="context")
        assert "students" not in tables.lower()

    def test_thread_isolation(
        self, setup_thread_context: None
    ) -> None:
        """Test that different threads have isolated TDB storage."""
        # Create table in default thread
        data = [{"id": 1, "value": "test"}]
        create_tdb_table(table_name="test_table", data=data, scope="context")

        # Switch to different thread
        set_thread_id("different_thread")

        # Table should not exist in different thread
        tables = list_tdb_tables(scope="context")
        assert "test_table" not in tables.lower()
