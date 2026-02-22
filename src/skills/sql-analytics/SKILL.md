---
name: sql-analytics
description: Database schema and business logic for sales data analysis including customers, orders, and revenue. Use when user asks about sales data, customer analytics, revenue reports, or SQL queries for business metrics.
---

# SQL Analytics Skill

## Overview

This skill provides database schema knowledge and business logic for sales data analysis.

## Database Schema

### customers

| Column | Type | Description |
|--------|------|-------------|
| customer_id | PRIMARY KEY | Unique customer identifier |
| name | TEXT | Customer full name |
| email | TEXT | Customer email address |
| signup_date | DATE | When customer registered |
| status | TEXT | 'active' or 'inactive' |
| customer_tier | TEXT | bronze/silver/gold/platinum |

### orders

| Column | Type | Description |
|--------|------|-------------|
| order_id | PRIMARY KEY | Unique order identifier |
| customer_id | FOREIGN KEY | References customers.customer_id |
| order_date | DATE | When order was placed |
| status | TEXT | pending/completed/cancelled/refunded |
| total_amount | DECIMAL | Order total in USD |
| sales_region | TEXT | north/south/east/west |

### order_items

| Column | Type | Description |
|--------|------|-------------|
| item_id | PRIMARY KEY | Unique line item identifier |
| order_id | FOREIGN KEY | References orders.order_id |
| product_id | TEXT | Product identifier |
| quantity | INTEGER | Number of units |
| unit_price | DECIMAL | Price per unit |
| discount_percent | DECIMAL | Discount applied (0-100) |

## Business Logic

### Active Customers
```sql
status = 'active' AND signup_date <= CURRENT_DATE - INTERVAL '90 days'
```

### Revenue Calculation
Only count orders with `status = 'completed'`. Use `total_amount` from orders table, which already accounts for discounts.

### Customer Lifetime Value (CLV)
Sum of all completed order amounts for a customer.

### High-Value Orders
Orders with `total_amount > 1000`

## Example Queries

### Top 10 Customers by Revenue (Last Quarter)

```sql
SELECT
    c.customer_id,
    c.name,
    c.customer_tier,
    SUM(o.total_amount) as total_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.status = 'completed'
  AND o.order_date >= CURRENT_DATE - INTERVAL '3 months'
GROUP BY c.customer_id, c.name, c.customer_tier
ORDER BY total_revenue DESC
LIMIT 10;
```

### Monthly Revenue Report

```sql
SELECT
    DATE_TRUNC('month', order_date) as month,
    COUNT(*) as order_count,
    SUM(total_amount) as revenue
FROM orders
WHERE status = 'completed'
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month DESC;
```

### Customers Without Orders (Last 6 Months)

```sql
SELECT c.customer_id, c.name, c.email
FROM customers c
WHERE NOT EXISTS (
    SELECT 1 FROM orders o
    WHERE o.customer_id = c.customer_id
    AND o.order_date >= CURRENT_DATE - INTERVAL '6 months'
    AND o.status = 'completed'
)
ORDER BY c.signup_date DESC;
```

## Best Practices

1. Always filter for `status = 'completed'` when calculating revenue
2. Use DATE_TRUNC for time-based aggregations
3. Consider customer_tier for segmentation analysis
4. Join with order_items for product-level analysis
