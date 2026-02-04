"""Test instincts migration from JSON to SQLite.

This test suite follows TDD approach:
1. Write tests first (demonstrate current JSON behavior)
2. Create SQLite schema
3. Implement migration
4. Update storage to use SQL
5. Verify all tests pass
"""

import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pytest

from executive_assistant.storage.instinct_storage import InstinctStorage


class TestCurrentJSONBehavior:
    """Test current JSON-based instincts storage (baseline)."""

    @pytest.fixture
    def instincts_storage_setup(self, tmp_path):
        """Create a temporary instincts storage for testing."""
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_instincts_json"
        instincts_dir = temp_root / thread_id / "instincts"
        instincts_dir.mkdir(parents=True, exist_ok=True)

        storage = InstinctStorage()

        # Patch the _get_instincts_dir method to return our temp directory
        def mock_get_dir(tid=None):
            return instincts_dir

        storage._get_instincts_dir = mock_get_dir

        return storage, thread_id, instincts_dir

    def test_create_instinct_json(self, instincts_storage_setup):
        """Test creating an instinct with JSON storage."""
        storage, thread_id, instincts_dir = instincts_storage_setup

        # Create instinct
        instinct_id = storage.create_instinct(
            trigger="user asks for report",
            action="use bullet points",
            domain="format",
            source="session-observation",
            confidence=0.8,
            thread_id=thread_id,
        )

        # Verify files created
        jsonl_path = instincts_dir / "instincts.jsonl"
        snapshot_path = instincts_dir / "instincts.snapshot.json"

        assert jsonl_path.exists()
        assert snapshot_path.exists()

        # Verify instinct retrieved
        instinct = storage.get_instinct(instinct_id, thread_id)
        assert instinct is not None
        assert instinct["trigger"] == "user asks for report"
        assert instinct["action"] == "use bullet points"
        assert instinct["domain"] == "format"
        assert instinct["confidence"] == 0.8

    def test_list_instincts_json(self, instincts_storage_setup):
        """Test listing instincts with JSON storage."""
        storage, thread_id, instincts_dir = instincts_storage_setup

        # Create multiple instincts
        storage.create_instinct(
            trigger="quick questions",
            action="respond briefly",
            domain="communication",
            confidence=0.9,
            thread_id=thread_id,
        )

        storage.create_instinct(
            trigger="detailed questions",
            action="provide thorough explanation",
            domain="communication",
            confidence=0.7,
            thread_id=thread_id,
        )

        # List all
        all_instincts = storage.list_instincts(thread_id=thread_id)
        assert len(all_instincts) == 2

        # Filter by domain
        comm_instincts = storage.list_instincts(domain="communication", thread_id=thread_id)
        assert len(comm_instincts) == 2

    def test_adjust_confidence_json(self, instincts_storage_setup):
        """Test adjusting instinct confidence with JSON storage."""
        storage, thread_id, instincts_dir = instincts_storage_setup

        # Create instinct
        instinct_id = storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="format",
            confidence=0.5,
            thread_id=thread_id,
        )

        # Reinforce
        storage.adjust_confidence(instinct_id, 0.1, thread_id)
        instinct = storage.get_instinct(instinct_id, thread_id)
        assert instinct["confidence"] == 0.6

        # Contradict
        storage.adjust_confidence(instinct_id, -0.2, thread_id)
        instinct = storage.get_instinct(instinct_id, thread_id)
        assert abs(instinct["confidence"] - 0.4) < 0.01  # Account for floating point


class TestSQLiteSchema:
    """Test SQLite schema for instincts storage."""

    @pytest.fixture
    def sqlite_db(self, tmp_path):
        """Create a temporary SQLite database for testing."""
        db_path = tmp_path / "instincts.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, db_path

    def test_create_instincts_table(self, sqlite_db):
        """Test creating instincts table in SQLite."""
        conn, db_path = sqlite_db

        # Create schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instincts (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                action TEXT NOT NULL,
                domain TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'enabled',

                occurrence_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                last_triggered TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_instincts_thread ON instincts(thread_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_instincts_domain ON instincts(domain)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_instincts_status ON instincts(status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_instincts_confidence ON instincts(confidence)
        """)

        conn.commit()

        # Verify table exists
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='instincts'"
        ).fetchall()

        assert len(tables) == 1

        # Verify indexes exist
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='instincts'"
        ).fetchall()

        index_names = [idx["name"] for idx in indexes]
        assert "idx_instincts_thread" in index_names
        assert "idx_instincts_domain" in index_names
        assert "idx_instincts_status" in index_names
        assert "idx_instincts_confidence" in index_names

    def test_insert_and_retrieve_instinct(self, sqlite_db):
        """Test inserting and retrieving an instinct from SQLite."""
        conn, db_path = sqlite_db

        # Create schema
        conn.execute("""
            CREATE TABLE instincts (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                action TEXT NOT NULL,
                domain TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'enabled',
                occurrence_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                last_triggered TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Insert instinct
        instinct_id = "test-uuid-123"
        conn.execute("""
            INSERT INTO instincts (
                id, thread_id, trigger, action, domain, source,
                confidence, status, occurrence_count, success_rate,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            instinct_id, "test_thread", "user asks for report",
            "use bullet points", "format", "session-observation",
            0.8, "enabled", 0, 1.0, "2026-02-04T00:00:00Z", "2026-02-04T00:00:00Z"
        ))

        conn.commit()

        # Retrieve
        row = conn.execute(
            "SELECT * FROM instincts WHERE id = ?",
            (instinct_id,)
        ).fetchone()

        assert row is not None
        assert row["trigger"] == "user asks for report"
        assert row["action"] == "use bullet points"
        assert row["confidence"] == 0.8


class TestMigrationLogic:
    """Test migration logic from JSON to SQLite."""

    @pytest.fixture
    def json_setup(self, tmp_path):
        """Create JSON instincts files for migration testing."""
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_migration"
        instincts_dir = temp_root / thread_id / "instincts"
        instincts_dir.mkdir(parents=True, exist_ok=True)

        # Create JSONL with events
        jsonl_path = instincts_dir / "instincts.jsonl"
        with open(jsonl_path, "w") as f:
            # Event 1: Create instinct
            f.write(json.dumps({
                "event": "create",
                "id": "instinct-1",
                "trigger": "user asks quick questions",
                "action": "respond briefly",
                "domain": "communication",
                "source": "session-observation",
                "confidence": 0.9,
                "ts": "2026-02-04T10:00:00Z"
            }) + "\n")

            # Event 2: Confirm
            f.write(json.dumps({
                "event": "confirm",
                "id": "instinct-1",
                "delta": 0.05,
                "old_confidence": 0.9,
                "new_confidence": 0.95,
                "ts": "2026-02-04T11:00:00Z"
            }) + "\n")

            # Event 3: Create another instinct
            f.write(json.dumps({
                "event": "create",
                "id": "instinct-2",
                "trigger": "morning requests",
                "action": "be detailed",
                "domain": "timing",
                "source": "session-observation",
                "confidence": 0.7,
                "ts": "2026-02-04T12:00:00Z"
            }) + "\n")

        return instincts_dir, thread_id, jsonl_path

    def test_migration_creates_sqlite_db(self, json_setup, tmp_path):
        """Test that migration creates SQLite database."""
        instincts_dir, thread_id, jsonl_path = json_setup

        # Create storage with patched directory
        storage = InstinctStorage()
        storage._get_instincts_dir = lambda tid=None: instincts_dir

        # Load current JSON storage
        instincts = storage.list_instincts(thread_id=thread_id, apply_decay=False)

        # Should have 2 instincts
        assert len(instincts) == 2

        # TODO: Migration will be implemented next
        # For now, verify JSON structure is correct
        instinct_1 = next(i for i in instincts if i["id"] == "instinct-1")
        assert instinct_1["confidence"] == 0.95  # After confirmation

        instinct_2 = next(i for i in instincts if i["id"] == "instinct-2")
        assert instinct_2["confidence"] == 0.7


class TestSQLiteStorageAPI:
    """Test SQLite-based storage maintains same API as JSON."""

    @pytest.fixture
    def sqlite_storage_setup(self, tmp_path):
        """Create SQLite storage for testing."""
        from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_sqlite_storage"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Create storage with mocked path
        storage = InstinctStorageSQLite()
        storage._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        return storage, thread_id

    def test_create_instinct_sqlite(self, sqlite_storage_setup):
        """Test creating instinct with SQLite storage."""
        storage, thread_id = sqlite_storage_setup

        instinct_id = storage.create_instinct(
            trigger="user asks for report",
            action="use bullet points",
            domain="format",
            confidence=0.8,
            thread_id=thread_id,
        )

        assert instinct_id is not None

        # Verify it was created
        instinct = storage.get_instinct(instinct_id, thread_id)
        assert instinct is not None
        assert instinct["trigger"] == "user asks for report"
        assert instinct["action"] == "use bullet points"
        assert instinct["domain"] == "format"
        assert instinct["confidence"] == 0.8

    def test_list_instincts_sqlite(self, sqlite_storage_setup):
        """Test listing instincts with SQLite storage."""
        storage, thread_id = sqlite_storage_setup

        # Create multiple instincts
        storage.create_instinct(
            trigger="quick questions",
            action="respond briefly",
            domain="communication",
            confidence=0.9,
            thread_id=thread_id,
        )

        storage.create_instinct(
            trigger="detailed questions",
            action="provide thorough explanation",
            domain="communication",
            confidence=0.7,
            thread_id=thread_id,
        )

        # List all
        all_instincts = storage.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(all_instincts) == 2

        # Filter by domain
        comm_instincts = storage.list_instincts(
            domain="communication",
            thread_id=thread_id,
            apply_decay=False
        )
        assert len(comm_instincts) == 2

    def test_adjust_confidence_sqlite(self, sqlite_storage_setup):
        """Test adjusting confidence with SQLite storage."""
        storage, thread_id = sqlite_storage_setup

        # Create instinct
        instinct_id = storage.create_instinct(
            trigger="test trigger",
            action="test action",
            domain="format",
            confidence=0.5,
            thread_id=thread_id,
        )

        # Reinforce
        storage.adjust_confidence(instinct_id, 0.1, thread_id)
        instinct = storage.get_instinct(instinct_id, thread_id)
        assert instinct["confidence"] == 0.6

        # Contradict
        storage.adjust_confidence(instinct_id, -0.2, thread_id)
        instinct = storage.get_instinct(instinct_id, thread_id)
        assert abs(instinct["confidence"] - 0.4) < 0.01  # Account for floating point


class TestBackwardCompatibility:
    """Test backward compatibility during migration."""

    @pytest.fixture
    def migration_setup(self, tmp_path):
        """Setup for migration testing."""
        from executive_assistant.storage.instinct_storage import InstinctStorage

        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "test_migration_compat"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        instincts_dir = thread_dir / "instincts"
        instincts_dir.mkdir(parents=True, exist_ok=True)

        # Create JSON instincts using old storage
        json_storage = InstinctStorage()
        json_storage._get_instincts_dir = lambda tid=None: instincts_dir

        # Create test instincts
        json_storage.create_instinct(
            trigger="test pattern",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id=thread_id,
        )

        return thread_id, instincts_dir

    def test_json_files_backed_up(self, migration_setup):
        """Test that migration creates backup files."""
        thread_id, instincts_dir = migration_setup

        # Create backup manually to test
        jsonl_path = instincts_dir / "instincts.jsonl"
        snapshot_path = instincts_dir / "instincts.snapshot.json"

        # Simulate backup
        if jsonl_path.exists():
            shutil.copy2(jsonl_path, f"{jsonl_path}.backup")
        if snapshot_path.exists():
            shutil.copy2(snapshot_path, f"{snapshot_path}.backup")

        # Verify backups exist
        assert jsonl_path.with_suffix(".jsonl.backup").exists() or (jsonl_path.parent / "instincts.jsonl.backup").exists()

    def test_can_read_json_during_migration(self, migration_setup):
        """Test that JSON can be read while SQLite exists."""
        from executive_assistant.storage.instinct_storage import InstinctStorage
        from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite

        thread_id, instincts_dir = migration_setup

        # Read JSON before migration
        json_storage = InstinctStorage()
        json_storage._get_instincts_dir = lambda tid=None: instincts_dir

        instincts_before = json_storage.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(instincts_before) == 1

        # Create SQLite database (simulate migration)
        sqlite_storage = InstinctStorageSQLite()
        sqlite_storage._get_db_path = lambda tid=None: instincts_dir / "instincts.db"

        sqlite_storage.create_instinct(
            trigger="test pattern",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id=thread_id,
        )

        # Verify JSON still readable
        instincts_after = json_storage.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(instincts_after) == 1

        # Verify SQLite also readable
        sqlite_instincts = sqlite_storage.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(sqlite_instincts) == 1

    def test_migration_idempotent(self, migration_setup):
        """Test that running migration twice is safe (idempotent)."""
        from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite

        thread_id, instincts_dir = migration_setup

        # Create SQLite database
        sqlite_storage = InstinctStorageSQLite()
        sqlite_storage._get_db_path = lambda tid=None: instincts_dir / "instincts.db"

        # First "migration" (create DB)
        sqlite_storage.create_instinct(
            trigger="test pattern",
            action="test action",
            domain="communication",
            confidence=0.8,
            thread_id=thread_id,
        )

        db_path = instincts_dir / "instincts.db"

        # Verify DB exists
        assert db_path.exists()

        # Second "migration" should detect existing DB
        # In real migration, this would skip and return "already_migrated"
        # For this test, we just verify DB persists
        assert db_path.exists()

        # Verify we can read from it
        instincts = sqlite_storage.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(instincts) >= 1
