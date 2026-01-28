"""Comprehensive tests for File tools.

This test suite covers all 10 File tools:
1. read_file
2. write_file
3. list_files
4. create_folder
5. delete_folder
6. rename_folder
7. delete_file
8. glob_files
9. grep_files
10. find_files_fuzzy
"""

import pytest
from typing import Generator
from pathlib import Path

from executive_assistant.storage.thread_storage import set_thread_id, get_thread_file_path
from executive_assistant.storage.file_sandbox import (
    read_file,
    write_file,
    list_files,
    create_folder,
    delete_folder,
    rename_folder,
    delete_file,
    glob_files,
    grep_files,
    find_files_fuzzy,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_thread_id() -> str:
    """Provide a test thread ID for isolated storage."""
    return "test_file_tools"


@pytest.fixture
def setup_thread_context(test_thread_id: str) -> Generator[None, None, None]:
    """Set up thread context for file operations."""
    set_thread_id(test_thread_id)
    yield
    # Cleanup happens automatically via test isolation


# =============================================================================
# Test: write_file
# =============================================================================

class TestWriteFile:
    """Tests for write_file tool."""

    def test_write_new_file(
        self, setup_thread_context: None
    ) -> None:
        """Test writing a new file."""
        result = write_file(
            file_path="test.txt",
            content="Hello, World!",
            scope="context"
        )

        assert "written" in result.lower() or "created" in result.lower()

        # Verify file exists
        file_path = get_thread_file_path("test_file_tools") / "test.txt"
        assert file_path.exists()

    def test_write_file_with_subdirs(
        self, setup_thread_context: None
    ) -> None:
        """Test writing a file to a subdirectory."""
        result = write_file(
            file_path="subdir/test.txt",
            content="Content in subdirectory",
            scope="context"
        )

        assert "written" in result.lower() or "created" in result.lower()

    def test_overwrite_existing_file(
        self, setup_thread_context: None
    ) -> None:
        """Test overwriting an existing file."""
        # Create initial file
        write_file(file_path="overwrite.txt", content="Original content", scope="context")

        # Overwrite
        result = write_file(
            file_path="overwrite.txt",
            content="Updated content",
            scope="context"
        )

        assert "written" in result.lower() or "overwritten" in result.lower()

        # Verify content changed
        content = read_file(file_path="overwrite.txt", scope="context")
        assert "Updated content" in content


# =============================================================================
# Test: read_file
# =============================================================================

class TestReadFile:
    """Tests for read_file tool."""

    def test_read_existing_file(
        self, setup_thread_context: None
    ) -> None:
        """Test reading an existing file."""
        # Write file first
        write_file(file_path="read_test.txt", content="Content to read", scope="context")

        # Read it back
        result = read_file(file_path="read_test.txt", scope="context")

        assert "Content to read" in result

    def test_read_nonexistent_file(
        self, setup_thread_context: None
    ) -> None:
        """Test reading a file that doesn't exist."""
        result = read_file(file_path="nonexistent.txt", scope="context")

        # Should handle error gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()

    def test_read_multiline_file(
        self, setup_thread_context: None
    ) -> None:
        """Test reading a file with multiple lines."""
        content = "Line 1\nLine 2\nLine 3"
        write_file(file_path="multiline.txt", content=content, scope="context")

        result = read_file(file_path="multiline.txt", scope="context")

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


# =============================================================================
# Test: create_folder
# =============================================================================

class TestCreateFolder:
    """Tests for create_folder tool."""

    def test_create_single_folder(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a single folder."""
        result = create_folder(
            folder_path="new_folder",
            scope="context"
        )

        assert "created" in result.lower()

    def test_create_nested_folders(
        self, setup_thread_context: None
    ) -> None:
        """Test creating nested folders."""
        result = create_folder(
            folder_path="parent/child/grandchild",
            scope="context"
        )

        assert "created" in result.lower()

    def test_create_existing_folder(
        self, setup_thread_context: None
    ) -> None:
        """Test creating a folder that already exists."""
        # Create folder first
        create_folder(folder_path="existing", scope="context")

        # Try to create again
        result = create_folder(
            folder_path="existing",
            scope="context"
        )

        # Should handle gracefully
        assert "exists" in result.lower() or "created" in result.lower()


# =============================================================================
# Test: list_files
# =============================================================================

class TestListFiles:
    """Tests for list_files tool."""

    def test_list_root_directory(
        self, setup_thread_context: None
    ) -> None:
        """Test listing files in root directory."""
        # Create some files
        write_file(file_path="file1.txt", content="Content 1", scope="context")
        write_file(file_path="file2.txt", content="Content 2", scope="context")

        result = list_files(directory="", scope="context")

        assert "file1.txt" in result.lower()
        assert "file2.txt" in result.lower()

    def test_list_subdirectory(
        self, setup_thread_context: None
    ) -> None:
        """Test listing files in a subdirectory."""
        create_folder(folder_path="subdir", scope="context")
        write_file(file_path="subdir/nested.txt", content="Nested content", scope="context")

        result = list_files(directory="subdir", scope="context")

        assert "nested.txt" in result.lower()

    def test_list_empty_directory(
        self, setup_thread_context: None
    ) -> None:
        """Test listing an empty directory."""
        create_folder(folder_path="empty_dir", scope="context")

        result = list_files(directory="empty_dir", scope="context")

        # Should handle empty directory gracefully
        assert "empty" in result.lower() or "no files" in result.lower() or len(result) == 0


# =============================================================================
# Test: rename_folder
# =============================================================================

class TestRenameFolder:
    """Tests for rename_folder tool."""

    def test_rename_folder(
        self, setup_thread_context: None
    ) -> None:
        """Test renaming a folder."""
        # Create folder
        create_folder(folder_path="old_name", scope="context")

        # Rename it
        result = rename_folder(
            old_path="old_name",
            new_path="new_name",
            scope="context"
        )

        assert "renamed" in result.lower()

    def test_rename_nonexistent_folder(
        self, setup_thread_context: None
    ) -> None:
        """Test renaming a folder that doesn't exist."""
        result = rename_folder(
            old_path="nonexistent",
            new_path="new_name",
            scope="context"
        )

        # Should handle error gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Test: delete_folder
# =============================================================================

class TestDeleteFolder:
    """Tests for delete_folder tool."""

    def test_delete_empty_folder(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting an empty folder."""
        # Create folder
        create_folder(folder_path="to_delete", scope="context")

        # Delete it
        result = delete_folder(
            folder_path="to_delete",
            scope="context"
        )

        assert "deleted" in result.lower()

    def test_delete_folder_with_files(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting a folder containing files."""
        # Create folder with files
        create_folder(folder_path="folder_with_files", scope="context")
        write_file(file_path="folder_with_files/file.txt", content="Content", scope="context")

        # Delete it
        result = delete_folder(
            folder_path="folder_with_files",
            scope="context"
        )

        assert "deleted" in result.lower()

    def test_delete_nonexistent_folder(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting a folder that doesn't exist."""
        result = delete_folder(
            folder_path="nonexistent_folder",
            scope="context"
        )

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Test: delete_file
# =============================================================================

class TestDeleteFile:
    """Tests for delete_file tool."""

    def test_delete_existing_file(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting an existing file."""
        # Create file
        write_file(file_path="to_delete.txt", content="Delete me", scope="context")

        # Delete it
        result = delete_file(
            file_path="to_delete.txt",
            scope="context"
        )

        assert "deleted" in result.lower()

    def test_delete_nonexistent_file(
        self, setup_thread_context: None
    ) -> None:
        """Test deleting a file that doesn't exist."""
        result = delete_file(
            file_path="nonexistent.txt",
            scope="context"
        )

        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower()


# =============================================================================
# Test: glob_files
# =============================================================================

class TestGlobFiles:
    """Tests for glob_files tool."""

    def test_glob_all_txt_files(
        self, setup_thread_context: None
    ) -> None:
        """Test globbing all .txt files."""
        # Create files
        write_file(file_path="file1.txt", content="Content 1", scope="context")
        write_file(file_path="file2.txt", content="Content 2", scope="context")
        write_file(file_path="document.md", content="Markdown", scope="context")

        result = glob_files(pattern="*.txt", directory="", scope="context")

        assert "file1.txt" in result.lower()
        assert "file2.txt" in result.lower()
        assert "document.md" not in result.lower()

    def test_glob_recursive(
        self, setup_thread_context: None
    ) -> None:
        """Test recursive globbing."""
        # Create nested structure
        create_folder(folder_path="sub", scope="context")
        write_file(file_path="sub/nested.txt", content="Nested", scope="context")
        write_file(file_path="root.txt", content="Root", scope="context")

        result = glob_files(pattern="**/*.txt", directory="", scope="context")

        assert "root.txt" in result.lower()
        assert "nested.txt" in result.lower()

    def test_glob_no_matches(
        self, setup_thread_context: None
    ) -> None:
        """Test globbing when no files match."""
        result = glob_files(pattern="*.xyz", directory="", scope="context")

        # Should handle no matches gracefully
        assert "no files" in result.lower() or "not found" in result.lower() or len(result) == 0


# =============================================================================
# Test: grep_files
# =============================================================================

class TestGrepFiles:
    """Tests for grep_files tool."""

    def test_grep_single_pattern(
        self, setup_thread_context: None
    ) -> None:
        """Test grepping for a single pattern."""
        # Create files
        write_file(file_path="file1.txt", content="Hello World\nPython is great", scope="context")
        write_file(file_path="file2.txt", content="Goodbye World\nJavaScript is cool", scope="context")

        result = grep_files(
            pattern="Python",
            directory="",
            scope="context"
        )

        assert "file1.txt" in result.lower() or "python" in result.lower()

    def test_grep_case_insensitive(
        self, setup_thread_context: None
    ) -> None:
        """Test case-insensitive grep."""
        write_file(file_path="case_test.txt", content="Hello HELLO hello", scope="context")

        result = grep_files(
            pattern="hello",
            directory="",
            scope="context"
        )

        # Should match all cases
        assert "hello" in result.lower()

    def test_grep_no_matches(
        self, setup_thread_context: None
    ) -> None:
        """Test grepping when no files match."""
        write_file(file_path="no_match.txt", content="This file has no matching words", scope="context")

        result = grep_files(
            pattern="nonexistent_pattern_xyz",
            directory="",
            scope="context"
        )

        # Should handle no matches gracefully
        assert "no matches" in result.lower() or "not found" in result.lower() or len(result) == 0


# =============================================================================
# Test: find_files_fuzzy
# =============================================================================

class TestFindFilesFuzzy:
    """Tests for find_files_fuzzy tool."""

    def test_find_fuzzy_by_name(
        self, setup_thread_context: None
    ) -> None:
        """Test fuzzy finding files by name."""
        # Create files
        write_file(file_path="document_2024.txt", content="Content", scope="context")
        write_file(file_path="doc_final.txt", content="Content", scope="context")
        write_file(file_path="readme.md", content="Content", scope="context")

        result = find_files_fuzzy(
            query="document",
            directory="",
            scope="context"
        )

        # Should find document-related files
        assert "document" in result.lower() or "doc" in result.lower()

    def test_find_fuzzy_no_results(
        self, setup_thread_context: None
    ) -> None:
        """Test fuzzy finding when no files match."""
        result = find_files_fuzzy(
            query="nonexistent_file_xyz",
            directory="",
            scope="context"
        )

        # Should handle no results gracefully
        assert "not found" in result.lower() or "no files" in result.lower() or len(result) == 0


# =============================================================================
# Integration Tests: Multi-Step Workflows
# =============================================================================

class TestFileWorkflows:
    """Integration tests for common file workflows."""

    def test_create_write_read_delete_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test complete file lifecycle: create, write, read, delete."""
        # 1. Write file
        write_file(file_path="lifecycle.txt", content="Test content", scope="context")

        # 2. Read file
        content = read_file(file_path="lifecycle.txt", scope="context")
        assert "Test content" in content

        # 3. List files (should include our file)
        result = list_files(directory="", scope="context")
        assert "lifecycle.txt" in result.lower()

        # 4. Delete file
        delete_file(file_path="lifecycle.txt", scope="context")

        # 5. Verify deletion
        result = list_files(directory="", scope="context")
        assert "lifecycle.txt" not in result.lower()

    def test_folder_hierarchy_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test working with folder hierarchies."""
        # 1. Create folder structure
        create_folder(folder_path="projects/web", scope="context")
        create_folder(folder_path="projects/data", scope="context")

        # 2. Write files in different folders
        write_file(
            file_path="projects/web/index.html",
            content="<html></html>",
            scope="context"
        )
        write_file(
            file_path="projects/data/analysis.py",
            content="# Data analysis",
            scope="context"
        )

        # 3. List files in projects folder
        result = list_files(directory="projects", scope="context")
        assert "web" in result.lower()
        assert "data" in result.lower()

        # 4. Glob all Python files
        result = glob_files(pattern="**/*.py", directory="", scope="context")
        assert "analysis.py" in result.lower()

        # 5. Clean up
        delete_folder(folder_path="projects", scope="context")

    def test_search_workflow(
        self, setup_thread_context: None
    ) -> None:
        """Test searching for content across files."""
        # Create files with content
        write_file(
            file_path="notes1.txt",
            content="TODO: Review pull request\nTODO: Write tests",
            scope="context"
        )
        write_file(
            file_path="notes2.txt",
            content="DONE: Fix bug\nTODO: Update docs",
            scope="context"
        )

        # Search for TODO
        result = grep_files(pattern="TODO", directory="", scope="context")
        assert "notes1.txt" in result.lower() or "notes2.txt" in result.lower()

        # Glob all notes files
        result = glob_files(pattern="notes*.txt", directory="", scope="context")
        assert "notes1.txt" in result.lower()

    def test_thread_isolation(
        self, setup_thread_context: None
    ) -> None:
        """Test that different threads have isolated file storage."""
        # Create file in default thread
        write_file(file_path="isolated.txt", content="Secret data", scope="context")

        # Should exist in default thread
        content = read_file(file_path="isolated.txt", scope="context")
        assert "Secret data" in content

        # Switch to different thread
        set_thread_id("different_thread")

        # File should not exist in different thread
        content = read_file(file_path="isolated.txt", scope="context")
        assert "Secret data" not in content
        assert "not found" in content.lower() or "does not exist" in content.lower()
