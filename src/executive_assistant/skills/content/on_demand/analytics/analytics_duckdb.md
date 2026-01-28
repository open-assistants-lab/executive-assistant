# Analytics with DuckDB

Description: Fast analytics and data processing using DuckDB (ADB) for large datasets, joins, aggregations, and complex queries

Tags: analytics, duckdb, adb, sql, data-analysis, queries, aggregation

## Overview

ADB (Analytics Database) is a DuckDB-powered analytics engine for fast data processing. Use it when you need:

- **Complex aggregations** (GROUP BY, window functions, CTEs)
- **Large file analysis** (CSV, Parquet, JSON direct queries)
- **Joins across datasets** (combine multiple tables/files)
- **Fast analytics** (columnar storage, vectorized execution)

## When to Use ADB vs TDB vs VDB

| Use Case | Storage | Why |
|----------|---------|-----|
| Complex queries, aggregations, joins | **ADB** | Optimized for analytics |
| Simple CRUD, transactional data | TDB | Better for frequent updates |
| Semantic search | VDB | Vector similarity |

## Available Tools

| Tool | Purpose |
|------|---------|
| `list_adb_tables` | Show available tables |
| `describe_adb_table` | Get table schema/columns |
| `show_adb_schema` | Overview of all tables |
| `query_adb` | Execute any SQL query |
| `create_adb_table` | Create table from JSON/CSV/data |
| `import_adb_csv` | Import CSV file into table |
| `export_adb_table` | Export table to CSV/JSON/Parquet |
| `drop_adb_table` | Delete a table |
| `optimize_adb` | Optimize database performance |

## Quick Start

### Check Available Tables
```python
list_adb_tables()
```

### See Table Structure
```python
describe_adb_table("timesheets")
```

### Run a Query
```python
query_adb("""
    SELECT 
        category,
        SUM(amount) as total,
        AVG(amount) as average
    FROM expenses
    GROUP BY category
    ORDER BY total DESC
""")
```

## Import Data

### From CSV File
```python
import_adb_csv("data/sales.csv", table_name="sales")
```

### From JSON Data
```python
# Python list (easier to write)
create_adb_table("users", data=[
    {"id": 1, "name": "Alice", "age": 30},
    {"id": 2, "name": "Bob", "age": 25}
])

# JSON string (also works)
create_adb_table("users", data='[{"id": 1, "name": "Alice", "age": 30}]')
```

### Direct File Query (No Import)
```python
query_adb("SELECT * FROM 'data/large_file.csv' LIMIT 10")
```

## Export Data

```python
# Export to CSV
export_adb_table("timesheets", "reports/timesheets.csv", format="csv")

# Export to JSON
export_adb_table("timesheets", "reports/timesheets.json", format="json")

# Export query results
export_adb_table("(SELECT * FROM timesheets WHERE hours > 8)", "overtime.csv")
```

## Common Patterns

### 1. Aggregate Analysis
```python
query_adb("""
    SELECT 
        strftime('%Y-%m', date) as month,
        SUM(hours) as total_hours,
        AVG(hours) as avg_hours,
        COUNT(DISTINCT project) as num_projects
    FROM timesheets
    GROUP BY month
    ORDER BY month
""")
```

### 2. Join Multiple Tables
```python
query_adb("""
    SELECT 
        t.project,
        SUM(t.hours) as total_hours,
        p.budget,
        p.manager
    FROM timesheets t
    JOIN projects p ON t.project_id = p.id
    WHERE t.date >= '2025-01-01'
    GROUP BY t.project
""")
```

### 3. Window Functions
```python
query_adb("""
    SELECT 
        date,
        hours,
        SUM(hours) OVER (ORDER BY date) as running_total,
        AVG(hours) OVER (ORDER BY date ROWS 6 PRECEDING) as moving_avg,
        RANK() OVER (ORDER BY hours DESC) as rank
    FROM timesheets
    ORDER BY date
""")
```

### 4. Time Series Analysis
```python
query_adb("""
    WITH daily AS (
        SELECT date, SUM(hours) as total
        FROM timesheets
        GROUP BY date
    )
    SELECT 
        date,
        total,
        total - LAG(total) OVER (ORDER BY date) as change,
        AVG(total) OVER (ORDER BY date ROWS 6 PRECEDING) as week_avg
    FROM daily
    ORDER BY date DESC
    LIMIT 30
""")
```

### 5. CTEs (Common Table Expressions)
```python
query_adb("""
    WITH 
    monthly_stats AS (
        SELECT 
            strftime('%Y-%m', date) as month,
            SUM(hours) as total_hours
        FROM timesheets
        GROUP BY month
    ),
    averages AS (
        SELECT AVG(total_hours) as avg_hours FROM monthly_stats
    )
    SELECT 
        m.month,
        m.total_hours,
        a.avg_hours,
        m.total_hours - a.avg_hours as diff
    FROM monthly_stats m
    CROSS JOIN averages a
    ORDER BY m.month
""")
```

## Data Management

### Create Table from Query
```python
query_adb("""
    CREATE TABLE monthly_summary AS
    SELECT 
        strftime('%Y-%m', date) as month,
        SUM(revenue) as total_revenue,
        SUM(cost) as total_cost
    FROM transactions
    GROUP BY month
""")
```

### Add Index for Performance
```python
query_adb("CREATE INDEX idx_date ON timesheets(date)")
query_adb("CREATE INDEX idx_project ON timesheets(project_id)")
```

### Drop Table
```python
drop_adb_table("old_temp_data")
```

### Optimize Database
```python
optimize_adb()
```

## DuckDB Features

### Supported SQL
- Standard SELECT, INSERT, UPDATE, DELETE
- JOINs (INNER, LEFT, RIGHT, FULL)
- Window functions (OVER, PARTITION BY)
- CTEs (WITH clauses)
- Subqueries
- Set operations (UNION, INTERSECT, EXCEPT)

### Data Types
- INTEGER, BIGINT, DOUBLE
- VARCHAR, TEXT
- DATE, TIMESTAMP
- BOOLEAN
- DECIMAL(precision, scale)

### Functions
- **Aggregation:** SUM, AVG, COUNT, MIN, MAX, STDDEV
- **String:** CONCAT, SUBSTRING, UPPER, LOWER, TRIM, LENGTH
- **Date:** strftime, date_trunc, EXTRACT, CURRENT_DATE
- **Math:** ABS, ROUND, FLOOR, CEIL, POWER, SQRT
- **Conditional:** CASE, COALESCE, NULLIF, IFNULL

## Workflows

### Workflow: Import CSV and Analyze
```python
# 1. Import CSV
import_adb_csv("data/sales.csv", table_name="sales")

# 2. Explore data
describe_adb_table("sales")

# 3. Complex analysis
query_adb("""
    SELECT 
        region,
        product,
        SUM(quantity) as units_sold,
        SUM(price * quantity) as revenue,
        AVG(price) as avg_price
    FROM sales
    GROUP BY region, product
    ORDER BY revenue DESC
    LIMIT 20
""")

# 4. Export results
export_adb_table("(SELECT * FROM sales WHERE revenue > 10000)", "top_sales.csv")
```

### Workflow: Compare Multiple Sources
```python
# Load data from different sources
import_adb_csv("data/q1_sales.csv", table_name="q1_sales")
import_adb_csv("data/q2_sales.csv", table_name="q2_sales")

# Compare quarters
query_adb("""
    SELECT 
        'Q1' as quarter,
        SUM(revenue) as total,
        COUNT(*) as transactions
    FROM q1_sales
    UNION ALL
    SELECT 
        'Q2' as quarter,
        SUM(revenue),
        COUNT(*)
    FROM q2_sales
""")
```

### Workflow: Data Cleaning Pipeline
```python
# 1. Load raw data
import_adb_csv("data/raw_customers.csv", table_name="customers_raw")

# 2. Create cleaned table
query_adb("""
    CREATE TABLE customers_clean AS
    SELECT 
        TRIM(UPPER(email)) as email,
        TRIM(name) as name,
        DATE_TRUNC('day', signup_date) as signup_date,
        CASE 
            WHEN country IN ('US', 'USA', 'United States') THEN 'USA'
            WHEN country IN ('UK', 'GB', 'United Kingdom') THEN 'UK'
            ELSE UPPER(country)
        END as country
    FROM customers_raw
    WHERE email IS NOT NULL
      AND email LIKE '%@%'
""")

# 3. Export clean data
export_adb_table("customers_clean", "customers_clean.csv")

# 4. Drop raw table
drop_adb_table("customers_raw")
```

## Best Practices

### ✅ DO
- Use ADB for read-heavy analytical queries
- Import data once, query many times
- Create indexes on frequently filtered columns
- Use `describe_adb_table` to check schema
- Export results for sharing
- Optimize database after large imports

### ❌ DON'T
- Use ADB for frequent single-row updates (use TDB instead)
- Load massive files without sampling first
- Forget to handle NULL values in queries
- Use `SELECT *` on wide tables unnecessarily
- Skip checking `list_adb_tables` before creating new tables

## Troubleshooting

### "No tables found"
ADB is empty. Either:
- Import data: `import_adb_csv()` or `create_adb_table()`
- Query external files: `query_adb("SELECT * FROM 'file.csv'")`

### "Column not found"
Check table schema:
```python
describe_adb_table("my_table")
```

### "Table already exists"
Use `if_exists=True` with `drop_adb_table`:
```python
drop_adb_table("old_table", if_exists=True)
```

### Performance Issues
- Add indexes: `query_adb("CREATE INDEX idx ON table(column)")`
- Use LIMIT for exploration: `query_adb("SELECT * FROM table LIMIT 100")`
- Filter early with WHERE clauses
- Run `optimize_adb()` after large changes

### Memory Issues
- Query files directly instead of importing
- Use `EXPORT` to save intermediate results
- Process data in chunks with LIMIT/OFFSET

## Quick Reference

| Task | Command |
|------|---------|
| List tables | `list_adb_tables()` |
| Describe table | `describe_adb_table("name")` |
| Show full schema | `show_adb_schema()` |
| Query | `query_adb("SELECT ...")` |
| Import CSV | `import_adb_csv("file.csv")` |
| Create table | `create_adb_table("name", data='[...]')` |
| Export | `export_adb_table("table", "out.csv")` |
| Drop table | `drop_adb_table("name")` |
| Optimize | `optimize_adb()` |

## Examples in Context

### Timesheet Analysis
```python
# Monthly hours by project
query_adb("""
    SELECT 
        project,
        strftime('%Y-%m', date) as month,
        SUM(hours) as total_hours,
        AVG(hours) as avg_daily
    FROM timesheets
    WHERE date >= '2025-01-01'
    GROUP BY project, month
    ORDER BY month, total_hours DESC
""")
```

### Expense Reporting
```python
# Monthly spending with running total
query_adb("""
    SELECT 
        strftime('%Y-%m', date) as month,
        category,
        SUM(amount) as total,
        SUM(SUM(amount)) OVER (ORDER BY strftime('%Y-%m', date)) as running_total
    FROM expenses
    GROUP BY month, category
    ORDER BY month, total DESC
""")
```

### Sales Dashboard Data
```python
# Top products with growth rate
query_adb("""
    WITH monthly_sales AS (
        SELECT 
            product,
            strftime('%Y-%m', date) as month,
            SUM(quantity) as units,
            SUM(price * quantity) as revenue
        FROM sales
        GROUP BY product, month
    )
    SELECT 
        product,
        month,
        revenue,
        revenue - LAG(revenue) OVER (PARTITION BY product ORDER BY month) as growth,
        RANK() OVER (ORDER BY revenue DESC) as rank
    FROM monthly_sales
    ORDER BY month DESC, revenue DESC
    LIMIT 50
""")
```
