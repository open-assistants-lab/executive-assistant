"""Unit tests for filesystem tools."""

import tempfile
from pathlib import Path
import pytest


class TestFilesystemOperations:
    """Tests for filesystem operations."""

    def test_write_and_read_file(self):
        """Test writing and reading a file."""
        import tempfile
        from src.tools.filesystem import write_file, read_file

        with tempfile.TemporaryDirectory() as tmpdir:
            write_file.invoke({"path": "test.txt", "content": "Hello World", "user_id": "test"})
            result = read_file.invoke({"path": "test.txt", "user_id": "test"})
            assert "Hello World" in result

    def test_delete_file(self):
        """Test deleting a file."""
        from src.tools.filesystem import delete_file, write_file

        with tempfile.TemporaryDirectory() as tmpdir:
            write_file.invoke({"path": "test.txt", "content": "To be deleted", "user_id": "test"})
            result = delete_file.invoke({"path": "test.txt", "user_id": "test"})
            assert "Deleted" in result
