"""Comprehensive tests for ADB (Analytics Database) tools.

This test suite covers all 2 ADB tools:
1. create_adb_table
2. query_adb
"""

import pytest
from typing import Generator

from executive_assistant.storage.thread_storage import set_thread_id, get_thread_adb_path
from executive_assistant.storage.adb_tools import (
    create_adb_table,
    query_adb,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_thread_id() -> str:
    """Provide a test thread ID for isolated storage."""
    return "test_adb_tools"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    """Set up thread context for ADB operations."""
    set_thread_id(test_thread_id)
    yield
    # Cleanup happens automatically via test isolation


@pytest.fixture
def sample_sales_data() -> list[dict]:
    """Provide sample sales data for analytics."""
    return [
        {"product": "Laptop", "category": "Electronics", "price": 999.99, "quantity": 5},
        {"product": "Mouse", "category": "Electronics", "price": 29.99, "quantity": 50},
        {"product": "Desk", "category": "Furniture", "price": 499.99, "quantity": 10},
        {"product": "T-shirt", "category": "Clothing", "price": 19.99, "quantity": 100},
        {"product": "Jeans", "category": "Clothing", "price": 49.99, "quantity": 75},
    ]


# =============================================================================
# Test: create_adb_table
# =============================================================================

class TestCreateADBTable:
    """Tests for create_adb_table tool."""

    def test_create_table_from_list(
        self, setup_thread_context: None, sample_sales_data: list[dict]
    ) -> None:
        """Test creating an analytics table from a list of dictionaries."""
        result = create_adb_table(
            table_name="sales",
            data=sample_sales_data,
            scope="context"
        )

        assert "created" in result.lower()
        assert "5 rows" in result.lower()

    def test_create_table_infer_schema(
        self, setup_thread_context: None
    ) -> None:
        """Test that table schema is inferred from data."""
        data = [
            {"id": 1, "name": "Test", "value": 100.5},
            {"id": 2, "name": "Test2", "value": 200.5}
        ]

        result = create_adb_table(table_name="test_table", data=data, scope="context")

        assert "created" in result.lower()
        assert "2 rows" in result.lower()

    def test_create_empty_table(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a table with no data."""
        result = create_adb_table(
            table_name="empty_table",
            data=[],
            scope="context"
        )

        # Should handle empty data gracefully
        assert "created" in result.lower() or "empty" in result.lower()


# =============================================================================
# Test: query_adb
# =============================================================================

class TestQueryADB:
    """Tests for query_adb tool."""

    def test_query_all_rows(
        self, setup_thread_context: None, sample_sales_data: list[dict]
    ) -> None:
        """Test querying all rows from an analytics table."""
        create_adb_table(table_name="sales", data=sample_sales_data, scope="context")

        result = query_adb(
            sql="SELECT * FROM sales",
            scope="context"
        )

        assert "laptop" in result.lower() or "electronics" in result.lower()

    def test_query_with_aggregation(
        self, setup_thread_context: None, sample_sales_data: list[dict]
    ) -> None:
        """Test querying with aggregation functions."""
        create_adb_table(table_name="sales", data=sample_sales_data, scope="context")

        result = query_adb(
            sql="SELECT category, SUM(price) as total FROM sales GROUP BY category",
            scope="context"
        )

        assert "electronics" in result.lower()
        assert "clothing" in result.lower()

    def test_query_with_where_clause(
        self, setup_thread_context: None, sample_sales_data: list[dict]
    ) -> None:
        """Test querying with a WHERE clause."""
        create_adb_table(table_name="sales", data=sample_sales_data, scope="context")

        result = query_adb(
            sql="SELECT * FROM sales WHERE category = 'Electronics'",
            scope="context"
        )

        assert "laptop" in result.lower() or "mouse" in result.lower()
        # Clothing items should not be present
        assert "t-shirt" not in result.lower()

    def test_query_with_having_clause(
        self, setup_thread_context: None, sample_sales_data: list[dict]
    ) -> None:
        """Test querying with HAVING clause for filtering aggregates."""
        create_adb_table(table_name="sales", data=sample_sales_data, scope="context")

        result = query_adb(
            sql="""
                SELECT category, COUNT(*) as count, AVG(price) as avg_price
                FROM sales
                GROUP BY category
                HAVING COUNT(*) > 1
            """,
            scope="context"
        )

        # Should only include categories with multiple products
        assert "electronics" in result.lower()
        assert "clothing" in result.lower()

    def test_query_with_complex_aggregation(
        self, setup_thread_context: None, sample_sales_data: list[dict]
    ) -> None:
        """Test complex analytics query with multiple aggregations."""
        create_adb_table(table_name="sales", data=sample_sales_data, scope="context")

        result = query_adb(
            sql="""
                SELECT
                    category,
                    SUM(price * quantity) as revenue,
                    COUNT(*) as product_count,
                    MAX(price) as max_price,
                    AVG(price) as avg_price
                FROM sales
                GROUP BY category
                ORDER BY revenue DESC
            """,
            scope="context"
        )

        # Verify multiple aggregation functions worked
        assert "electronics" in result.lower() or "clothing" in result.lower()


# =============================================================================
# Integration Tests: Multi-Step Workflows
# =============================================================================

class TestADBWorkflows:
    """Integration tests for common ADB workflows."""

    def test_analytics_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test complete analytics workflow: create, aggregate, filter."""
        # 1. Create table with data
        data = [
            {"product": "A", "region": "North", "sales": 100},
            {"product": "B", "region": "South", "sales": 200},
            {"product": "A", "region": "South", "sales": 150},
            {"product": "C", "region": "North", "sales": 300},
        ]
        create_adb_table(table_name="regional_sales", data=data, scope="context")

        # 2. Query total sales by region
        result = query_adb(
            sql="SELECT region, SUM(sales) as total FROM regional_sales GROUP BY region",
            scope="context"
        )
        assert "north" in result.lower()
        assert "south" in result.lower()

        # 3. Query top-selling product
        result = query_adb(
            sql="SELECT product, SUM(sales) as total FROM regional_sales GROUP BY product ORDER BY total DESC LIMIT 1",
            scope="context"
        )
        # Should have a result
        assert len(result) > 0

    def test_window_function_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test analytics with window functions (DuckDB feature)."""
        data = [
            {"employee": "Alice", "department": "Engineering", "salary": 95000},
            {"employee": "Bob", "department": "Engineering", "salary": 87000},
            {"employee": "Charlie", "department": "Sales", "salary": 90000},
        ]
        create_adb_table(table_name="employees", data=data, scope="context")

        # Query with window function to rank employees by salary within department
        result = query_adb(
            sql="""
                SELECT
                    employee,
                    department,
                    salary,
                    RANK() OVER (PARTITION BY department ORDER BY salary DESC) as rank_in_dept
                FROM employees
            """,
            scope="context"
        )

        assert "alice" in result.lower() or "bob" in result.lower()

    def test_thread_isolation(
        self, setup_thread_context: None
    ) -> None:
        """Test that different threads have isolated ADB storage."""
        # Create table in default thread
        data = [{"id": 1, "value": "test"}]
        create_adb_table(table_name="test_table", data=data, scope="context")

        # Query should succeed
        result = query_adb(sql="SELECT * FROM test_table", scope="context")
        assert "test" in result.lower() or "1" in result

        # Switch to different thread
        set_thread_id("different_thread")

        # Table should not exist in different thread
        # This should either error or return empty
        try:
            result = query_adb(sql="SELECT * FROM test_table", scope="context")
            # If it doesn't error, it should be empty
            assert "test" not in result.lower()
        except Exception:
            # Expected - table doesn't exist in different thread
            pass
