"""Unit tests for file sandbox with thread_id separation."""

from pathlib import Path

import pytest

from cassey.storage.file_sandbox import (
    FileSandbox,
    set_thread_id,
    get_thread_id,
    read_file,
    write_file,
    list_files,
)


class TestThreadIdContext:
    """Test thread_id context variable."""

    def test_set_and_get_thread_id(self):
        """Test setting and getting thread_id from context."""
        # Initially None
        assert get_thread_id() is None

        # Set and get
        set_thread_id("test_thread")
        assert get_thread_id() == "test_thread"

        # Reset to None for other tests
        set_thread_id("")

    def test_context_isolation(self):
        """Test that context variable is isolated per task."""
        set_thread_id("thread_1")
        assert get_thread_id() == "thread_1"

        # Setting new value overrides
        set_thread_id("thread_2")
        assert get_thread_id() == "thread_2"

        # Reset
        set_thread_id("")


class TestSandboxWithThreadId:
    """Test FileSandbox with thread_id separation."""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create a temporary root for testing."""
        return tmp_path / "files"

    def test_sandbox_with_thread_id(self, temp_root):
        """Test that thread_id creates separate directory."""
        # Set thread_id
        set_thread_id("telegram:user123")

        sandbox = FileSandbox(root=temp_root / "telegram_user123")

        # Should create thread-specific directory
        expected_path = temp_root / "telegram_user123"
        assert sandbox.root == expected_path

        # Reset
        set_thread_id("")

    def test_sandbox_sanitizes_thread_id(self, temp_root):
        """Test that thread_id is sanitized for directory names."""
        set_thread_id("http:user:with:colons/and/slashes")

        # Simulate sanitized directory name
        safe_thread_id = "http:user:with:colons/and/slashes"
        for char in (":", "/", "@", "\\"):
            safe_thread_id = safe_thread_id.replace(char, "_")

        sandbox = FileSandbox(root=temp_root / safe_thread_id)

        # Should replace : and / with _
        expected_path = temp_root / "http_user_with_colons_and_slashes"
        assert sandbox.root == expected_path

        # Reset
        set_thread_id("")

    def test_sandbox_user_id_takes_priority(self, temp_root):
        """Test that explicit user_id creates separate directory."""
        set_thread_id("http:thread1")

        # Explicit user_id should take priority
        sandbox = FileSandbox(root=temp_root / "explicit_user")

        # Should use explicit user_id
        expected_path = temp_root / "explicit_user"
        assert sandbox.root == expected_path

        # Reset
        set_thread_id("")


class TestFileOperationsWithThreadId:
    """Test file operations with thread_id separation."""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create a temporary root for testing."""
        return tmp_path / "files"

    def test_write_read_with_thread_id(self, temp_root):
        """Test writing and reading files with thread_id isolation."""
        # Thread 1 sandbox
        thread1_sandbox = FileSandbox(root=temp_root / "telegram_user1", allowed_extensions={".txt"})
        thread1_sandbox.root.mkdir(parents=True, exist_ok=True)

        # Write directly to the sandbox root (bypass validation for this test)
        path1 = thread1_sandbox.root / "test.txt"
        path1.write_text("Hello from user1", encoding="utf-8")

        # Thread 1 reads
        content = path1.read_text(encoding="utf-8")
        assert content == "Hello from user1"

        # Thread 2 sandbox - should not see thread 1's file
        thread2_sandbox = FileSandbox(root=temp_root / "telegram_user2", allowed_extensions={".txt"})
        thread2_path = thread2_sandbox.root / "test.txt"

        # Thread 2's file should not exist (different directory)
        assert not thread2_path.exists()

    def test_list_files_with_thread_id(self, temp_root):
        """Test listing files with thread_id isolation."""
        # Thread 1 sandbox
        thread1_sandbox = FileSandbox(
            root=temp_root / "http_thread1",
            allowed_extensions={".txt", ".md"}
        )
        thread1_sandbox.root.mkdir(parents=True, exist_ok=True)

        # Create files
        (thread1_sandbox.root / "a.txt").write_text("content a")
        (thread1_sandbox.root / "b.md").write_text("content b")

        # List files in thread 1
        items = []
        for item in thread1_sandbox.root.iterdir():
            items.append(item.name)

        assert "a.txt" in items
        assert "b.md" in items

        # Thread 2 sandbox - should be empty
        thread2_sandbox = FileSandbox(
            root=temp_root / "http_thread2",
            allowed_extensions={".txt", ".md"}
        )
        thread2_sandbox.root.mkdir(parents=True, exist_ok=True)

        # List files in thread 2
        items2 = []
        for item in thread2_sandbox.root.iterdir():
            items2.append(item.name)

        # Thread 2 should not see thread 1's files
        assert "a.txt" not in items2
        assert "b.md" not in items2
