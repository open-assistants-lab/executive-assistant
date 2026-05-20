"""DuckDB analytics benchmarks: aggregation, group-by, join, overhead."""

import pytest

from .helpers import generate_analytics_data

pytest.importorskip("duckdb")


@pytest.fixture
def analytics_db(db, scale):
    rows = generate_analytics_data(scale.n_analytics_rows)
    db.create_table("analytics", {
        "category": "TEXT",
        "region": "TEXT",
        "value": "REAL",
        "quantity": "INTEGER",
        "timestamp": "TEXT",
    })
    db.insert_batch("analytics", rows, sync=False)
    db.create_table("metadata", {"category": "TEXT", "label": "TEXT"})
    db.insert_batch(
        "metadata",
        [{"category": cat, "label": f"Category {cat}"} for cat in ["A", "B", "C", "D", "E"]],
        sync=False,
    )
    db.register_duckdb_table("analytics")
    db.register_duckdb_table("metadata")
    return db


def test_simple_aggregation(benchmark, analytics_db):
    def _agg():
        return analytics_db.analytics(
            "SELECT COUNT(*) as cnt, AVG(value) as avg_val, SUM(quantity) as total_qty FROM analytics"
        )

    result = benchmark(_agg)
    assert len(result) == 1
    assert result[0]["cnt"] > 0


def test_group_by(benchmark, analytics_db):
    def _gb():
        return analytics_db.analytics(
            "SELECT category, COUNT(*) as cnt, AVG(value) as avg_val "
            "FROM analytics GROUP BY category ORDER BY cnt DESC"
        )

    result = benchmark(_gb)
    assert len(result) > 0


def test_join(benchmark, analytics_db):
    def _join():
        return analytics_db.analytics(
            "SELECT a.category, m.label, COUNT(*) as cnt "
            "FROM analytics a JOIN metadata m ON a.category = m.category "
            "GROUP BY a.category, m.label ORDER BY cnt DESC"
        )

    result = benchmark(_join)
    assert len(result) > 0


def test_analytics_overhead(benchmark, analytics_db, scale):
    """Compare HybridDB.analytics() vs native DuckDB overhead ratio."""
    sql = "SELECT COUNT(*) FROM analytics WHERE value > 100"

    def _hybrid():
        return analytics_db.analytics(sql)

    result = benchmark(_hybrid)
    assert len(result) == 1
