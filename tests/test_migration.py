"""Tests for data migration to consolidated per-thread storage."""

import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from cassey.config import settings


class TestPathHelpers:
    """Test new path helper functions in settings."""

    def test_sanitize_thread_id(self):
        """Test thread_id sanitization."""
        # Test various special characters
        assert settings._sanitize_thread_id("telegram:user123") == "telegram_user123"
        assert settings._sanitize_thread_id("http:user@example.com") == "http_user_example.com"
        assert settings._sanitize_thread_id("a/b\\c:d") == "a_b_c_d"
        assert settings._sanitize_thread_id("normal") == "normal"

    def test_get_thread_root(self):
        """Test get_thread_root returns correct path."""
        thread_id = "telegram:user123"
        root = settings.get_thread_root(thread_id)

        expected = settings.USERS_ROOT / "telegram_user123"
        assert root == expected.resolve()

    def test_get_thread_files_path_new_layout(self, tmp_path):
        """Test get_thread_files_path uses new layout when it exists."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"):
            thread_id = "telegram:user123"
            new_path = settings.USERS_ROOT / "telegram_user123" / "files"
            new_path.mkdir(parents=True)

            result = settings.get_thread_files_path(thread_id)
            assert result == new_path.resolve()

    def test_get_thread_files_path_fallback(self, tmp_path):
        """Test get_thread_files_path falls back to old layout."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "FILES_ROOT", tmp_path / "data" / "files"):
            thread_id = "telegram:user123"

            # Create old layout
            old_path = settings.FILES_ROOT / "telegram_user123"
            old_path.mkdir(parents=True)

            result = settings.get_thread_files_path(thread_id)
            assert result == old_path.resolve()

    def test_get_thread_db_path_new_layout(self, tmp_path):
        """Test get_thread_db_path uses new layout when it exists."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"):
            thread_id = "telegram:user123"
            new_path = settings.USERS_ROOT / "telegram_user123" / "db" / "main.db"
            new_path.parent.mkdir(parents=True)
            new_path.touch()

            result = settings.get_thread_db_path(thread_id)
            assert result == new_path.resolve()

    def test_get_thread_db_path_fallback(self, tmp_path):
        """Test get_thread_db_path falls back to old layout."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "DB_ROOT", tmp_path / "data" / "db"):
            thread_id = "telegram:user123"

            # Create old layout
            old_path = settings.DB_ROOT / "telegram_user123.db"
            old_path.parent.mkdir(parents=True)
            old_path.touch()

            result = settings.get_thread_db_path(thread_id)
            assert result == old_path.resolve()

    def test_get_thread_kb_path_new_layout(self, tmp_path):
        """Test get_thread_kb_path uses new layout when it exists."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"):
            thread_id = "telegram:user123"
            new_path = settings.USERS_ROOT / "telegram_user123" / "kb" / "main.db"
            new_path.parent.mkdir(parents=True)
            new_path.touch()

            result = settings.get_thread_kb_path(thread_id)
            assert result == new_path.resolve()

    def test_get_thread_kb_path_fallback(self, tmp_path):
        """Test get_thread_kb_path falls back to old layout."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "KB_ROOT", tmp_path / "data" / "kb"):
            thread_id = "telegram:user123"

            # Create old layout
            old_path = settings.KB_ROOT / "telegram_user123.db"
            old_path.parent.mkdir(parents=True)
            old_path.touch()

            result = settings.get_thread_kb_path(thread_id)
            assert result == old_path.resolve()

    def test_is_new_storage_layout(self, tmp_path):
        """Test is_new_storage_layout detection."""
        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"):
            thread_id = "telegram:user123"

            # Old layout only
            assert not settings.is_new_storage_layout(thread_id)

            # Create new layout
            new_path = settings.USERS_ROOT / "telegram_user123"
            new_path.mkdir(parents=True)

            assert settings.is_new_storage_layout(thread_id)


class TestMigrationPathResolution:
    """Test that storage classes use new paths correctly."""

    def test_file_sandbox_uses_new_path(self, tmp_path):
        """Test FileSandbox uses new path when available."""
        from cassey.storage.file_sandbox import set_thread_id, get_sandbox

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "FILES_ROOT", tmp_path / "data" / "files"):

            thread_id = "telegram:user123"
            set_thread_id(thread_id)

            # Create new layout
            new_path = settings.USERS_ROOT / "telegram_user123" / "files"
            new_path.mkdir(parents=True)

            sandbox = get_sandbox()
            assert sandbox.root == new_path.resolve()

            set_thread_id("")

    def test_file_sandbox_fallback_to_old(self, tmp_path):
        """Test FileSandbox falls back to old path."""
        from cassey.storage.file_sandbox import set_thread_id, get_sandbox

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "FILES_ROOT", tmp_path / "data" / "files"):

            thread_id = "telegram:user123"
            set_thread_id(thread_id)

            # Create old layout
            old_path = settings.FILES_ROOT / "telegram_user123"
            old_path.mkdir(parents=True)

            sandbox = get_sandbox()
            assert sandbox.root == old_path.resolve()

            set_thread_id("")

    def test_db_storage_uses_new_path(self, tmp_path):
        """Test DBStorage uses new path when available."""
        from cassey.storage.db_storage import DBStorage
        from cassey.storage.file_sandbox import set_thread_id

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "DB_ROOT", tmp_path / "data" / "db"):

            thread_id = "telegram:user123"
            set_thread_id(thread_id)

            # Create new layout
            new_path = settings.USERS_ROOT / "telegram_user123" / "db" / "main.db"
            new_path.parent.mkdir(parents=True)
            new_path.touch()

            storage = DBStorage()
            db_path = storage._get_db_path()
            assert db_path == new_path.resolve()

            set_thread_id("")

    def test_db_storage_fallback_to_old(self, tmp_path):
        """Test DBStorage falls back to old path."""
        from cassey.storage.db_storage import DBStorage
        from cassey.storage.file_sandbox import set_thread_id

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "DB_ROOT", tmp_path / "data" / "db"):

            thread_id = "telegram:user123"
            set_thread_id(thread_id)

            # Create old layout
            old_path = settings.DB_ROOT / "telegram_user123.db"
            old_path.parent.mkdir(parents=True)
            old_path.touch()

            storage = DBStorage()
            db_path = storage._get_db_path()
            assert db_path == old_path.resolve()

            set_thread_id("")

    def test_kb_storage_uses_new_path(self, tmp_path):
        """Test KBStorage uses new path when available."""
        from cassey.storage.kb_storage import KBStorage
        from cassey.storage.file_sandbox import set_thread_id

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "KB_ROOT", tmp_path / "data" / "kb"):

            thread_id = "telegram:user123"
            set_thread_id(thread_id)

            # Create new layout
            new_path = settings.USERS_ROOT / "telegram_user123" / "kb" / "main.db"
            new_path.parent.mkdir(parents=True)
            new_path.touch()

            storage = KBStorage()
            kb_path = storage._get_db_path()
            assert kb_path == new_path.resolve()

            set_thread_id("")

    def test_kb_storage_fallback_to_old(self, tmp_path):
        """Test KBStorage falls back to old path."""
        from cassey.storage.kb_storage import KBStorage
        from cassey.storage.file_sandbox import set_thread_id

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "KB_ROOT", tmp_path / "data" / "kb"):

            thread_id = "telegram:user123"
            set_thread_id(thread_id)

            # Create old layout
            old_path = settings.KB_ROOT / "telegram_user123.db"
            old_path.parent.mkdir(parents=True)
            old_path.touch()

            storage = KBStorage()
            kb_path = storage._get_db_path()
            assert kb_path == old_path.resolve()

            set_thread_id("")


class TestMigrationIntegration:
    """Integration tests for migration logic."""

    @pytest.fixture
    def old_layout_setup(self, tmp_path):
        """Set up old layout structure for testing migration."""
        data_root = tmp_path / "data"
        files_root = data_root / "files"
        db_root = data_root / "db"
        kb_root = data_root / "kb"

        files_root.mkdir(parents=True)
        db_root.mkdir(parents=True)
        kb_root.mkdir(parents=True)

        # Create thread data
        thread_id = "telegram_user123"
        thread_files = files_root / thread_id
        thread_files.mkdir(parents=True)

        # Add some files
        (thread_files / "test.txt").write_text("Hello, world!")
        (thread_files / "subdir").mkdir()
        (thread_files / "subdir" / "nested.txt").write_text("Nested content")

        # Create database
        db_path = db_root / f"{thread_id}.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test_table VALUES (1, 'test')")
        conn.commit()
        conn.close()

        # Create KB
        kb_path = kb_root / f"{thread_id}.db"
        conn = sqlite3.connect(str(kb_path))
        conn.execute("CREATE TABLE kb_table (id INTEGER, content TEXT)")
        conn.execute("INSERT INTO kb_table VALUES (1, 'knowledge')")
        conn.commit()
        conn.close()

        return {
            "data_root": data_root,
            "files_root": files_root,
            "db_root": db_root,
            "kb_root": kb_root,
            "thread_id": thread_id,
        }

    def test_migrate_files_structure(self, old_layout_setup):
        """Test that files are migrated correctly."""
        from scripts.migrate_data import migrate_thread

        thread_id = old_layout_setup["thread_id"]
        data_root = old_layout_setup["data_root"]
        files_root = old_layout_setup["files_root"]

        with patch.object(settings, "USERS_ROOT", data_root / "users"), \
             patch.object(settings, "FILES_ROOT", files_root), \
             patch.object(settings, "DB_ROOT", data_root / "db"), \
             patch.object(settings, "KB_ROOT", data_root / "kb"):
            result = migrate_thread(thread_id, dry_run=False)

            assert result["success"]
            assert result["files_migrated"] == 2  # test.txt and nested.txt

            # Verify new structure
            new_files_path = settings.USERS_ROOT / thread_id / "files"
            assert new_files_path.exists()
            assert (new_files_path / "test.txt").read_text() == "Hello, world!"
            assert (new_files_path / "subdir" / "nested.txt").read_text() == "Nested content"

    def test_migrate_database(self, old_layout_setup):
        """Test that database is migrated correctly."""
        from scripts.migrate_data import migrate_thread

        thread_id = old_layout_setup["thread_id"]
        data_root = old_layout_setup["data_root"]
        db_root = old_layout_setup["db_root"]

        with patch.object(settings, "USERS_ROOT", data_root / "users"), \
             patch.object(settings, "FILES_ROOT", data_root / "files"), \
             patch.object(settings, "DB_ROOT", db_root), \
             patch.object(settings, "KB_ROOT", data_root / "kb"):
            result = migrate_thread(thread_id, dry_run=False)

            assert result["success"]
            assert result["db_migrated"]

            # Verify database integrity
            new_db_path = settings.USERS_ROOT / thread_id / "db" / "main.db"
            assert new_db_path.exists()

            conn = sqlite3.connect(str(new_db_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()
            conn.close()

            assert integrity[0] == "ok"

    def test_migrate_kb(self, old_layout_setup):
        """Test that KB is migrated correctly."""
        from scripts.migrate_data import migrate_thread

        thread_id = old_layout_setup["thread_id"]
        data_root = old_layout_setup["data_root"]
        kb_root = old_layout_setup["kb_root"]

        with patch.object(settings, "USERS_ROOT", data_root / "users"), \
             patch.object(settings, "FILES_ROOT", data_root / "files"), \
             patch.object(settings, "DB_ROOT", data_root / "db"), \
             patch.object(settings, "KB_ROOT", kb_root):
            result = migrate_thread(thread_id, dry_run=False)

            assert result["success"]
            assert result["kb_migrated"]

            # Verify KB integrity
            new_kb_path = settings.USERS_ROOT / thread_id / "kb" / "main.db"
            assert new_kb_path.exists()

            conn = sqlite3.connect(str(new_kb_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()
            conn.close()

            assert integrity[0] == "ok"

    def test_verify_migration(self, old_layout_setup):
        """Test migration verification."""
        from scripts.migrate_data import migrate_thread, verify_migration

        thread_id = old_layout_setup["thread_id"]
        data_root = old_layout_setup["data_root"]

        with patch.object(settings, "USERS_ROOT", data_root / "users"), \
             patch.object(settings, "FILES_ROOT", data_root / "files"), \
             patch.object(settings, "DB_ROOT", data_root / "db"), \
             patch.object(settings, "KB_ROOT", data_root / "kb"):
            # Migrate
            migrate_thread(thread_id, dry_run=False)

            # Verify
            results = verify_migration([thread_id])

            assert results["verified_threads"] == 1
            assert len(results["failed_threads"]) == 0

    def test_rollback_migration(self, old_layout_setup):
        """Test migration rollback."""
        from scripts.migrate_data import migrate_thread, rollback_migration

        thread_id = old_layout_setup["thread_id"]
        data_root = old_layout_setup["data_root"]

        with patch.object(settings, "USERS_ROOT", data_root / "users"), \
             patch.object(settings, "FILES_ROOT", data_root / "files"), \
             patch.object(settings, "DB_ROOT", data_root / "db"), \
             patch.object(settings, "KB_ROOT", data_root / "kb"):
            # Migrate
            migrate_thread(thread_id, dry_run=False)

            # Verify new layout exists
            new_root = settings.USERS_ROOT / thread_id
            assert new_root.exists()

            # Rollback
            results = rollback_migration([thread_id])

            assert results["rolled_back_threads"] == 1
            assert not new_root.exists()

            # Old data should still be there
            assert old_layout_setup["files_root"].exists()
            assert old_layout_setup["db_root"].exists()
            assert old_layout_setup["kb_root"].exists()


class TestMigrationEdgeCases:
    """Test edge cases in migration."""

    def test_thread_with_special_characters(self, tmp_path):
        """Test migration with thread_id containing special characters."""
        from scripts.migrate_data import migrate_thread

        data_root = tmp_path / "data"
        files_root = data_root / "files"
        users_root = data_root / "users"

        with patch.object(settings, "USERS_ROOT", users_root), \
             patch.object(settings, "FILES_ROOT", files_root), \
             patch.object(settings, "DB_ROOT", data_root / "db"), \
             patch.object(settings, "KB_ROOT", data_root / "kb"):

            # Thread ID with special characters
            thread_id = "http:user:with@special\\chars"
            safe_thread_id = "http_user_with_special_chars"

            # Create old layout
            old_path = settings.FILES_ROOT / safe_thread_id
            old_path.mkdir(parents=True)
            (old_path / "test.txt").write_text("content")

            # Migrate
            result = migrate_thread(thread_id, dry_run=False)

            assert result["success"]
            assert (settings.USERS_ROOT / safe_thread_id / "files" / "test.txt").exists()

    def test_partial_data_migration(self, tmp_path):
        """Test migration when only some data types exist."""
        from scripts.migrate_data import migrate_thread

        with patch.object(settings, "USERS_ROOT", tmp_path / "data" / "users"), \
             patch.object(settings, "FILES_ROOT", tmp_path / "data" / "files"), \
             patch.object(settings, "DB_ROOT", tmp_path / "data" / "db"), \
             patch.object(settings, "KB_ROOT", tmp_path / "data" / "kb"):

            thread_id = "telegram_user123"

            # Only create files, no DB or KB
            old_path = settings.FILES_ROOT / thread_id
            old_path.mkdir(parents=True)
            (old_path / "test.txt").write_text("content")

            # Migrate
            result = migrate_thread(thread_id, dry_run=False)

            assert result["success"]
            assert result["files_migrated"] == 1
            assert not result["db_migrated"]
            assert not result["kb_migrated"]
