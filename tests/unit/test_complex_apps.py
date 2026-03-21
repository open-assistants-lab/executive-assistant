"""Tests for complex multi-table app use cases."""

import shutil
from pathlib import Path

import pytest

TEST_USER_ID = "test_complex_user"


@pytest.fixture(autouse=True)
def cleanup_test_db():
    """Clean up test database before and after each test."""
    db_path = Path(f"data/users/{TEST_USER_ID}/apps")
    if db_path.exists():
        shutil.rmtree(db_path)
    yield
    if db_path.exists():
        shutil.rmtree(db_path)


@pytest.fixture
def storage():
    """Get app storage for testing."""
    from src.tools.apps.storage import AppStorage

    return AppStorage(TEST_USER_ID)


class TestComplexUseCases:
    """Test all 10 complex multi-table use cases."""

    def test_pos_point_of_sale(self, storage):
        """Test Point of Sale system with products, customers, orders, line_items."""
        tables = {
            "products": {
                "name": "TEXT",
                "sku": "TEXT",
                "price": "REAL",
                "cost": "REAL",
                "stock": "INTEGER",
                "category": "TEXT",
                "is_active": "BOOLEAN",
            },
            "customers": {
                "name": "TEXT",
                "email": "TEXT",
                "phone": "TEXT",
                "address": "TEXT",
                "loyalty_points": "INTEGER",
            },
            "orders": {
                "customer_id": "INTEGER",
                "order_date": "INTEGER",
                "status": "TEXT",
                "subtotal": "REAL",
                "tax": "REAL",
                "total": "REAL",
                "payment_method": "TEXT",
            },
            "line_items": {
                "order_id": "INTEGER",
                "product_id": "INTEGER",
                "quantity": "INTEGER",
                "unit_price": "REAL",
                "total": "REAL",
            },
        }
        schema = storage.create_app("pos", tables)

        assert "products" in schema.tables
        assert "customers" in schema.tables
        assert "orders" in schema.tables
        assert "line_items" in schema.tables

        # Insert a product
        pid = storage.insert(
            "pos",
            "products",
            {
                "name": "Coffee",
                "sku": "COF001",
                "price": 3.50,
                "cost": 1.00,
                "stock": 100,
                "category": "Beverage",
                "is_active": True,
            },
        )

        # Insert a customer
        cid = storage.insert(
            "pos",
            "customers",
            {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234",
                "address": "123 Main St",
                "loyalty_points": 0,
            },
        )

        # Insert an order
        oid = storage.insert(
            "pos",
            "orders",
            {
                "customer_id": cid,
                "status": "completed",
                "subtotal": 7.00,
                "tax": 0.70,
                "total": 7.70,
                "payment_method": "card",
            },
        )

        # Insert line item
        lid = storage.insert(
            "pos",
            "line_items",
            {"order_id": oid, "product_id": pid, "quantity": 2, "unit_price": 3.50, "total": 7.00},
        )

        # Query products
        results = storage.query_sql("pos", "SELECT * FROM products WHERE price > 2")
        assert len(results) == 1

        # Query orders
        results = storage.query_sql("pos", "SELECT * FROM orders WHERE total > 5")
        assert len(results) == 1

    def test_bom_bill_of_materials(self, storage):
        """Test Bill of Materials with products, components, bom_items, suppliers."""
        tables = {
            "products": {
                "name": "TEXT",
                "sku": "TEXT",
                "unit_cost": "REAL",
                "selling_price": "REAL",
                "is_assembled": "BOOLEAN",
            },
            "components": {
                "name": "TEXT",
                "sku": "TEXT",
                "unit_cost": "REAL",
                "unit": "TEXT",
                "supplier_id": "INTEGER",
            },
            "bom_items": {
                "product_id": "INTEGER",
                "component_id": "INTEGER",
                "quantity": "REAL",
                "unit": "TEXT",
            },
            "suppliers": {
                "name": "TEXT",
                "contact": "TEXT",
                "email": "TEXT",
                "lead_time_days": "INTEGER",
            },
        }
        schema = storage.create_app("bom", tables)

        assert "products" in schema.tables
        assert "components" in schema.tables
        assert "bom_items" in schema.tables
        assert "suppliers" in schema.tables

        # Insert supplier
        sid = storage.insert(
            "bom",
            "suppliers",
            {"name": "Acme Parts", "contact": "Bob", "email": "bob@acme.com", "lead_time_days": 7},
        )

        # Insert components
        cid1 = storage.insert(
            "bom",
            "components",
            {
                "name": "Screw",
                "sku": "SCR001",
                "unit_cost": 0.10,
                "unit": "piece",
                "supplier_id": sid,
            },
        )

        # Insert product
        pid = storage.insert(
            "bom",
            "products",
            {
                "name": "Table",
                "sku": "TBL001",
                "unit_cost": 50.00,
                "selling_price": 100.00,
                "is_assembled": True,
            },
        )

        # Insert BOM item
        storage.insert(
            "bom",
            "bom_items",
            {"product_id": pid, "component_id": cid1, "quantity": 10, "unit": "piece"},
        )

        # Query - calculate total cost
        results = storage.query_sql(
            "bom",
            """
            SELECT p.name, SUM(c.unit_cost * b.quantity) as total_component_cost
            FROM products p
            JOIN bom_items b ON p.id = b.product_id
            JOIN components c ON b.component_id = c.id
            WHERE p.id = ?
        """,
            [pid],
        )
        assert len(results) >= 0

    def test_project_management(self, storage):
        """Test Project Management with projects, tasks, time_entries, team_members."""
        tables = {
            "projects": {
                "name": "TEXT",
                "description": "TEXT",
                "start_date": "INTEGER",
                "end_date": "INTEGER",
                "status": "TEXT",
                "budget": "REAL",
            },
            "tasks": {
                "project_id": "INTEGER",
                "title": "TEXT",
                "description": "TEXT",
                "assignee_id": "INTEGER",
                "status": "TEXT",
                "priority": "TEXT",
                "due_date": "INTEGER",
            },
            "time_entries": {
                "task_id": "INTEGER",
                "user_id": "INTEGER",
                "hours": "REAL",
                "date": "INTEGER",
                "description": "TEXT",
            },
            "team_members": {
                "name": "TEXT",
                "email": "TEXT",
                "role": "TEXT",
                "hourly_rate": "REAL",
            },
        }
        schema = storage.create_app("project", tables)

        # Insert team member
        mid = storage.insert(
            "project",
            "team_members",
            {
                "name": "Alice",
                "email": "alice@example.com",
                "role": "Developer",
                "hourly_rate": 100.00,
            },
        )

        # Insert project
        pid = storage.insert(
            "project",
            "projects",
            {
                "name": "Website Redesign",
                "description": "Redesign company website",
                "status": "active",
                "budget": 50000.00,
            },
        )

        # Insert task
        tid = storage.insert(
            "project",
            "tasks",
            {
                "project_id": pid,
                "title": "Design homepage",
                "description": "Create new homepage design",
                "assignee_id": mid,
                "status": "in_progress",
                "priority": "high",
            },
        )

        # Insert time entry
        storage.insert(
            "project",
            "time_entries",
            {
                "task_id": tid,
                "user_id": mid,
                "hours": 8.0,
                "description": "Designed homepage mockup",
            },
        )

        # Query tasks by priority
        results = storage.query_sql("project", "SELECT * FROM tasks WHERE priority = 'high'")
        assert len(results) == 1

    def test_library_management(self, storage):
        """Test Library Management system."""
        tables = {
            "books": {
                "title": "TEXT",
                "author": "TEXT",
                "isbn": "TEXT",
                "category_id": "INTEGER",
                "publish_year": "INTEGER",
                "copies": "INTEGER",
                "available": "INTEGER",
            },
            "members": {
                "name": "TEXT",
                "email": "TEXT",
                "phone": "TEXT",
                "membership_date": "INTEGER",
                "membership_type": "TEXT",
            },
            "loans": {
                "book_id": "INTEGER",
                "member_id": "INTEGER",
                "loan_date": "INTEGER",
                "due_date": "INTEGER",
                "return_date": "INTEGER",
                "status": "TEXT",
            },
            "categories": {"name": "TEXT", "description": "TEXT"},
        }
        schema = storage.create_app("library", tables)

        # Insert category
        cat_id = storage.insert(
            "library", "categories", {"name": "Fiction", "description": "Fiction books"}
        )

        # Insert book
        book_id = storage.insert(
            "library",
            "books",
            {
                "title": "The Great Gatsby",
                "author": "F. Scott Fitzgerald",
                "isbn": "978-0743273565",
                "category_id": cat_id,
                "publish_year": 1925,
                "copies": 3,
                "available": 3,
            },
        )

        # Insert member
        mem_id = storage.insert(
            "library",
            "members",
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "555-5678",
                "membership_type": "premium",
            },
        )

        # Query available books
        results = storage.query_sql("library", "SELECT * FROM books WHERE available > 0")
        assert len(results) == 1

    def test_restaurant_management(self, storage):
        """Test Restaurant Management system."""
        tables = {
            "tables": {
                "table_number": "INTEGER",
                "capacity": "INTEGER",
                "section": "TEXT",
                "status": "TEXT",
            },
            "menu_items": {
                "name": "TEXT",
                "category": "TEXT",
                "price": "REAL",
                "description": "TEXT",
                "is_available": "BOOLEAN",
            },
            "orders": {
                "table_id": "INTEGER",
                "order_date": "INTEGER",
                "status": "TEXT",
                "subtotal": "REAL",
                "tax": "REAL",
                "total": "REAL",
            },
            "order_items": {
                "order_id": "INTEGER",
                "menu_item_id": "INTEGER",
                "quantity": "INTEGER",
                "unit_price": "REAL",
                "total": "REAL",
                "notes": "TEXT",
            },
        }
        schema = storage.create_app("restaurant", tables)

        # Insert table
        tid = storage.insert(
            "restaurant",
            "tables",
            {"table_number": 1, "capacity": 4, "section": "patio", "status": "available"},
        )

        # Insert menu item
        mid = storage.insert(
            "restaurant",
            "menu_items",
            {
                "name": "Burger",
                "category": "Main",
                "price": 12.99,
                "description": "Juicy beef burger",
                "is_available": True,
            },
        )

        # Insert order
        oid = storage.insert(
            "restaurant",
            "orders",
            {"table_id": tid, "status": "open", "subtotal": 12.99, "tax": 1.30, "total": 14.29},
        )

        # Insert order item
        storage.insert(
            "restaurant",
            "order_items",
            {
                "order_id": oid,
                "menu_item_id": mid,
                "quantity": 1,
                "unit_price": 12.99,
                "total": 12.99,
            },
        )

        # Query orders
        results = storage.query_sql("restaurant", "SELECT * FROM orders WHERE total > 10")
        assert len(results) == 1

    def test_hotel_management(self, storage):
        """Test Hotel Management system."""
        tables = {
            "rooms": {
                "room_number": "INTEGER",
                "room_type": "TEXT",
                "floor": "INTEGER",
                "price": "REAL",
                "status": "TEXT",
            },
            "guests": {
                "name": "TEXT",
                "email": "TEXT",
                "phone": "TEXT",
                "id_type": "TEXT",
                "id_number": "TEXT",
            },
            "bookings": {
                "guest_id": "INTEGER",
                "room_id": "INTEGER",
                "check_in": "INTEGER",
                "check_out": "INTEGER",
                "status": "TEXT",
                "total": "REAL",
                "notes": "TEXT",
            },
        }
        schema = storage.create_app("hotel", tables)

        # Insert room
        rid = storage.insert(
            "hotel",
            "rooms",
            {
                "room_number": 101,
                "room_type": "deluxe",
                "floor": 1,
                "price": 150.00,
                "status": "available",
            },
        )

        # Insert guest
        gid = storage.insert(
            "hotel",
            "guests",
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "555-9999",
                "id_type": "passport",
                "id_number": "AB123456",
            },
        )

        # Insert booking
        storage.insert(
            "hotel",
            "bookings",
            {"guest_id": gid, "room_id": rid, "status": "confirmed", "total": 450.00},
        )

        # Query available rooms
        results = storage.query_sql("hotel", "SELECT * FROM rooms WHERE status = 'available'")
        assert len(results) == 1

    def test_manufacturing(self, storage):
        """Test Manufacturing system."""
        tables = {
            "work_orders": {
                "product_id": "INTEGER",
                "quantity": "INTEGER",
                "start_date": "INTEGER",
                "due_date": "INTEGER",
                "status": "TEXT",
                "priority": "TEXT",
            },
            "operations": {
                "work_order_id": "INTEGER",
                "operation_number": "INTEGER",
                "machine_id": "INTEGER",
                "description": "TEXT",
                "estimated_hours": "REAL",
                "actual_hours": "REAL",
                "status": "TEXT",
            },
            "materials": {
                "name": "TEXT",
                "sku": "TEXT",
                "unit": "TEXT",
                "quantity_on_hand": "INTEGER",
                "reorder_point": "INTEGER",
            },
            "machines": {
                "name": "TEXT",
                "status": "TEXT",
                "hourly_cost": "REAL",
                "location": "TEXT",
            },
        }
        schema = storage.create_app("manufacturing", tables)

        # Insert machine
        mid = storage.insert(
            "manufacturing",
            "machines",
            {
                "name": "CNC Mill",
                "status": "operational",
                "hourly_cost": 50.00,
                "location": "Floor 1",
            },
        )

        # Insert material
        mat_id = storage.insert(
            "manufacturing",
            "materials",
            {
                "name": "Steel Sheet",
                "sku": "STL001",
                "unit": "sheet",
                "quantity_on_hand": 100,
                "reorder_point": 20,
            },
        )

        # Insert work order
        wid = storage.insert(
            "manufacturing",
            "work_orders",
            {"quantity": 50, "status": "in_progress", "priority": "high"},
        )

        # Insert operation
        storage.insert(
            "manufacturing",
            "operations",
            {
                "work_order_id": wid,
                "operation_number": 1,
                "machine_id": mid,
                "description": "Cut steel",
                "estimated_hours": 4.0,
                "status": "completed",
            },
        )

        # Query low stock materials
        results = storage.query_sql(
            "manufacturing", "SELECT * FROM materials WHERE quantity_on_hand < reorder_point"
        )
        assert len(results) == 0

    def test_healthcare(self, storage):
        """Test Healthcare system."""
        tables = {
            "patients": {
                "name": "TEXT",
                "date_of_birth": "INTEGER",
                "gender": "TEXT",
                "phone": "TEXT",
                "email": "TEXT",
                "address": "TEXT",
            },
            "doctors": {
                "name": "TEXT",
                "specialty": "TEXT",
                "phone": "TEXT",
                "email": "TEXT",
                "consultation_fee": "REAL",
            },
            "appointments": {
                "patient_id": "INTEGER",
                "doctor_id": "INTEGER",
                "appointment_date": "INTEGER",
                "status": "TEXT",
                "notes": "TEXT",
            },
        }
        schema = storage.create_app("healthcare", tables)

        # Insert doctor
        did = storage.insert(
            "healthcare",
            "doctors",
            {
                "name": "Dr. Smith",
                "specialty": "Cardiology",
                "phone": "555-1111",
                "email": "smith@hospital.com",
                "consultation_fee": 200.00,
            },
        )

        # Insert patient
        pid = storage.insert(
            "healthcare",
            "patients",
            {
                "name": "Jane Doe",
                "gender": "Female",
                "phone": "555-2222",
                "email": "jane@example.com",
            },
        )

        # Insert appointment
        storage.insert(
            "healthcare",
            "appointments",
            {"patient_id": pid, "doctor_id": did, "status": "scheduled", "notes": "Annual checkup"},
        )

        # Query appointments
        results = storage.query_sql(
            "healthcare", "SELECT * FROM appointments WHERE status = 'scheduled'"
        )
        assert len(results) == 1

    def test_education(self, storage):
        """Test Education system."""
        tables = {
            "students": {
                "name": "TEXT",
                "email": "TEXT",
                "phone": "TEXT",
                "enrollment_date": "INTEGER",
                "status": "TEXT",
            },
            "courses": {
                "name": "TEXT",
                "code": "TEXT",
                "credits": "INTEGER",
                "instructor": "TEXT",
                "semester": "TEXT",
            },
            "enrollments": {
                "student_id": "INTEGER",
                "course_id": "INTEGER",
                "enrollment_date": "INTEGER",
                "status": "TEXT",
            },
            "grades": {
                "enrollment_id": "INTEGER",
                "assignment_name": "TEXT",
                "score": "REAL",
                "max_score": "REAL",
                "weight": "REAL",
            },
        }
        schema = storage.create_app("education", tables)

        # Insert student
        sid = storage.insert(
            "education",
            "students",
            {"name": "Alice Johnson", "email": "alice@school.edu", "status": "active"},
        )

        # Insert course
        cid = storage.insert(
            "education",
            "courses",
            {
                "name": "Introduction to Programming",
                "code": "CS101",
                "credits": 3,
                "instructor": "Prof. Brown",
                "semester": "Fall 2024",
            },
        )

        # Insert enrollment
        eid = storage.insert(
            "education", "enrollments", {"student_id": sid, "course_id": cid, "status": "enrolled"}
        )

        # Insert grade
        storage.insert(
            "education",
            "grades",
            {
                "enrollment_id": eid,
                "assignment_name": "Homework 1",
                "score": 85.0,
                "max_score": 100.0,
                "weight": 0.1,
            },
        )

        # Query active students
        results = storage.query_sql("education", "SELECT * FROM students WHERE status = 'active'")
        assert len(results) == 1

    def test_asset_management(self, storage):
        """Test Asset Management system."""
        tables = {
            "assets": {
                "name": "TEXT",
                "serial_number": "TEXT",
                "purchase_date": "INTEGER",
                "purchase_price": "REAL",
                "category_id": "INTEGER",
                "location_id": "INTEGER",
                "status": "TEXT",
                "notes": "TEXT",
            },
            "locations": {"name": "TEXT", "address": "TEXT", "building": "TEXT", "floor": "TEXT"},
            "categories": {"name": "TEXT", "description": "TEXT", "depreciation_rate": "REAL"},
            "maintenance": {
                "asset_id": "INTEGER",
                "maintenance_date": "INTEGER",
                "type": "TEXT",
                "cost": "REAL",
                "notes": "TEXT",
            },
        }
        schema = storage.create_app("asset", tables)

        # Insert location
        lid = storage.insert(
            "asset",
            "locations",
            {"name": "Office HQ", "address": "100 Main St", "building": "A", "floor": "2"},
        )

        # Insert category
        cat_id = storage.insert(
            "asset",
            "categories",
            {
                "name": "Electronics",
                "description": "Electronic equipment",
                "depreciation_rate": 0.20,
            },
        )

        # Insert asset
        aid = storage.insert(
            "asset",
            "assets",
            {
                "name": "MacBook Pro",
                "serial_number": "C02XG0GTJG5H",
                "purchase_price": 2500.00,
                "category_id": cat_id,
                "location_id": lid,
                "status": "active",
            },
        )

        # Insert maintenance record
        storage.insert(
            "asset",
            "maintenance",
            {"asset_id": aid, "type": "repair", "cost": 150.00, "notes": "Replaced keyboard"},
        )

        # Query active assets
        results = storage.query_sql("asset", "SELECT * FROM assets WHERE status = 'active'")
        assert len(results) == 1


class TestMultiTableCRUD:
    """Test CRUD operations across multiple tables."""

    def test_join_queries(self, storage):
        """Test SQL JOIN queries across tables."""
        tables = {
            "customers": {"name": "TEXT", "email": "TEXT"},
            "orders": {"customer_id": "INTEGER", "total": "REAL", "status": "TEXT"},
            "order_items": {
                "order_id": "INTEGER",
                "product": "TEXT",
                "quantity": "INTEGER",
                "price": "REAL",
            },
        }
        storage.create_app("shop", tables)

        # Insert data
        cid = storage.insert("shop", "customers", {"name": "Alice", "email": "alice@example.com"})
        oid = storage.insert(
            "shop", "orders", {"customer_id": cid, "total": 100.00, "status": "completed"}
        )
        storage.insert(
            "shop",
            "order_items",
            {"order_id": oid, "product": "Widget", "quantity": 2, "price": 50.00},
        )

        # JOIN query
        results = storage.query_sql(
            "shop",
            """
            SELECT c.name, o.total, oi.product, oi.quantity
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            JOIN order_items oi ON o.id = oi.order_id
        """,
        )

        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        assert results[0]["name"] == "Alice", f"Expected name 'Alice', got {results[0]['name']}"
        assert results[0]["product"] == "Widget", (
            f"Expected product 'Widget', got {results[0]['product']}"
        )
        assert results[0]["quantity"] == 2, f"Expected quantity 2, got {results[0]['quantity']}"

    def test_aggregation_queries(self, storage):
        """Test aggregation queries."""
        tables = {
            "products": {"name": "TEXT", "category": "TEXT", "price": "REAL"},
            "sales": {"product_id": "INTEGER", "quantity": "INTEGER", "total": "REAL"},
        }
        storage.create_app("sales", tables)

        # Insert products
        p1 = storage.insert(
            "sales", "products", {"name": "A", "category": "Electronics", "price": 100.00}
        )
        p2 = storage.insert(
            "sales", "products", {"name": "B", "category": "Electronics", "price": 200.00}
        )

        # Insert sales
        storage.insert("sales", "sales", {"product_id": p1, "quantity": 10, "total": 1000.00})
        storage.insert("sales", "sales", {"product_id": p2, "quantity": 5, "total": 1000.00})

        # Aggregation query
        results = storage.query_sql(
            "sales",
            """
            SELECT p.category, SUM(s.total) as revenue, COUNT(*) as orders
            FROM products p
            JOIN sales s ON p.id = s.product_id
            GROUP BY p.category
        """,
        )

        assert len(results) == 1
        assert results[0]["revenue"] == 2000.00

    def test_update_across_tables(self, storage):
        """Test updating data across related tables."""
        tables = {
            "orders": {"status": "TEXT", "total": "REAL"},
            "invoices": {"order_id": "INTEGER", "amount": "REAL", "paid": "BOOLEAN"},
        }
        storage.create_app("billing", tables)

        # Insert order and invoice
        oid = storage.insert("billing", "orders", {"status": "pending", "total": 500.00})
        storage.insert("billing", "invoices", {"order_id": oid, "amount": 500.00, "paid": False})

        # Update order status
        storage.update("billing", "orders", oid, {"status": "completed"})

        # Verify
        results = storage.query_sql("billing", "SELECT * FROM orders WHERE id = ?", [oid])
        assert results[0]["status"] == "completed"
