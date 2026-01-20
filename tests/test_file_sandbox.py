"""Tests for FileSandbox and file operations."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from executive_assistant.storage.file_sandbox import (
    FileSandbox,
    SecurityError,
    set_thread_id,
    get_thread_id,
    clear_thread_id,
    set_user_id,
    get_user_id,
    get_sandbox,
)
from executive_assistant.storage.group_storage import set_group_id, clear_group_id


# =============================================================================
# Thread ID Context Tests
# =============================================================================

class TestThreadIdContext:
    """Test thread_id context variable management."""

    def test_set_and_get_thread_id(self):
        """Test setting and getting thread_id from context."""
        clear_thread_id()
        assert get_thread_id() is None

        set_thread_id("test_thread")
        assert get_thread_id() == "test_thread"

        clear_thread_id()

    def test_context_isolation(self):
        """Test that context variable persists until cleared."""
        clear_thread_id()
        set_thread_id("thread_1")
        assert get_thread_id() == "thread_1"

        # New value overrides
        set_thread_id("thread_2")
        assert get_thread_id() == "thread_2"

        clear_thread_id()


# =============================================================================
# FileSandbox Tests
# =============================================================================

class TestFileSandbox:
    """Test FileSandbox class."""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create a temporary root for testing."""
        root = tmp_path / "files"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def sandbox(self, temp_root):
        """Create a FileSandbox instance with temp root."""
        return FileSandbox(
            root=temp_root,
            allowed_extensions={".txt", ".md", ".json", ".csv"},
            max_file_size_mb=10
        )

    def test_init_default(self, tmp_path):
        """Test FileSandbox initialization with defaults."""
        sandbox = FileSandbox(root=tmp_path / "files")
        assert sandbox.root is not None
        assert sandbox.allowed_extensions is not None
        assert sandbox.max_file_size_mb > 0

    def test_init_custom(self, temp_root):
        """Test FileSandbox initialization with custom values."""
        sandbox = FileSandbox(
            root=temp_root,
            allowed_extensions={".py", ".js"},
            max_file_size_mb=5
        )
        assert sandbox.root == temp_root.resolve()
        assert sandbox.allowed_extensions == {".py", ".js"}
        assert sandbox.max_file_size_mb == 5
        assert sandbox.max_bytes == 5 * 1024 * 1024

    def test_validate_path_within_sandbox(self, sandbox):
        """Test path validation for paths within sandbox."""
        result = sandbox._validate_path("test.txt")
        assert result.name == "test.txt"
        assert result.parent == sandbox.root

    def test_validate_path_with_subdirectory(self, sandbox):
        """Test path validation with subdirectory."""
        result = sandbox._validate_path("docs/notes.txt")
        assert "docs" in result.parts
        assert "notes.txt" in result.parts

    def test_validate_path_traversal_blocked(self, sandbox):
        """Test that path traversal attacks are blocked."""
        with pytest.raises(SecurityError, match="Path traversal blocked"):
            sandbox._validate_path("../etc/passwd")

        with pytest.raises(SecurityError, match="Path traversal blocked"):
            sandbox._validate_path("/etc/passwd")

    def test_validate_path_extension_allowed(self, sandbox):
        """Test that allowed extensions pass validation."""
        sandbox._validate_path("test.txt")  # Should not raise
        sandbox._validate_path("test.md")   # Should not raise
        sandbox._validate_path("test.json") # Should not raise

    def test_validate_path_extension_blocked(self, sandbox):
        """Test that blocked extensions are rejected."""
        with pytest.raises(SecurityError, match="File type.*not allowed"):
            sandbox._validate_path("test.exe")

        with pytest.raises(SecurityError, match="File type.*not allowed"):
            sandbox._validate_path("test.sh")

    def test_validate_size_within_limit(self, sandbox):
        """Test content size validation within limit."""
        small_content = "a" * 100  # 100 bytes
        sandbox._validate_size(small_content)  # Should not raise

    def test_validate_size_exceeds_limit(self, sandbox):
        """Test content size validation exceeds limit."""
        large_content = "a" * (11 * 1024 * 1024)  # 11 MB
        with pytest.raises(SecurityError, match="File size.*exceeds limit"):
            sandbox._validate_size(large_content)

    def test_write_and_read_file(self, sandbox):
        """Test writing and reading a file."""
        content = "Hello, world!"

        # Write file
        validated_path = sandbox._validate_path("test.txt")
        validated_path.write_text(content, encoding="utf-8")

        # Read file
        result = validated_path.read_text(encoding="utf-8")
        assert result == content

    def test_list_files_empty(self, sandbox):
        """Test listing files in empty directory."""
        files = list(sandbox.root.iterdir())
        assert len(files) == 0

    def test_mkdir_p(self, sandbox):
        """Test creating nested directories."""
        nested = sandbox.root / "level1" / "level2"
        nested.mkdir(parents=True, exist_ok=True)
        assert nested.exists()
        assert nested.is_dir()


# =============================================================================
# get_sandbox Tests
# =============================================================================

class TestGetSandbox:
    """Test get_sandbox function with different routing strategies."""

    def test_get_sandbox_with_user_id(self, tmp_path):
        """Test get_sandbox with explicit user_id."""
        expected = tmp_path / "files" / "test_user"
        mock_settings = MagicMock()
        mock_settings.get_user_files_path.return_value = expected
        mock_settings.ALLOWED_FILE_EXTENSIONS = {".txt", ".md"}
        mock_settings.MAX_FILE_SIZE_MB = 10

        with patch("executive_assistant.storage.file_sandbox.settings", mock_settings):
            sandbox = get_sandbox(user_id="test_user")
            assert sandbox.root == expected.resolve()
            assert sandbox.root.exists()

    def test_get_sandbox_with_group_id_context(self, tmp_path):
        """Test get_sandbox with group_id from context."""
        # Create expected directory structure
        groups_root = tmp_path / "data" / "groups"
        groups_root.mkdir(parents=True, exist_ok=True)
        expected = groups_root / "test_group" / "files"
        expected.mkdir(parents=True, exist_ok=True)

        mock_settings = MagicMock()
        mock_settings.get_group_files_path.return_value = expected
        mock_settings.ALLOWED_FILE_EXTENSIONS = {".txt", ".md"}
        mock_settings.MAX_FILE_SIZE_MB = 10
        mock_settings.get_user_files_path.return_value = tmp_path / "files"

        with patch("executive_assistant.storage.file_sandbox.settings", mock_settings):
            # Set group_id context
            from executive_assistant.storage.group_storage import set_group_id
            set_group_id("test_group")
            try:
                sandbox = get_sandbox()
                assert sandbox.root == expected.resolve()
            finally:
                # Clear context to avoid affecting other tests
                set_group_id("")

    def test_get_sandbox_with_thread_id_context(self, tmp_path):
        """Test get_sandbox with thread_id from context."""
        users_root = tmp_path / "data" / "users"
        users_root.mkdir(parents=True, exist_ok=True)
        expected = users_root / "anon_telegram_user123" / "files"
        expected.mkdir(parents=True, exist_ok=True)

        # Use MagicMock for settings
        mock_settings = MagicMock()
        mock_settings.get_user_files_path.return_value = expected
        mock_settings.ALLOWED_FILE_EXTENSIONS = {".txt", ".md"}
        mock_settings.MAX_FILE_SIZE_MB = 10
        mock_settings.get_user_files_path.return_value = expected

        with patch("executive_assistant.storage.file_sandbox.settings", mock_settings):
            # Set thread_id context
            set_thread_id("telegram:user123")
            try:
                sandbox = get_sandbox()
                assert sandbox.root == expected.resolve()
            finally:
                # Clear context
                clear_thread_id()

    def test_get_sandbox_fallback_to_global(self):
        """Test get_sandbox falls back to global sandbox when no context is set."""
        # Clear any existing context
        from executive_assistant.storage.group_storage import clear_group_id
        clear_group_id()
        clear_thread_id()

        # Mock context functions to return empty/None
        with patch("executive_assistant.storage.file_sandbox.get_workspace_id", return_value=""):
            with patch("executive_assistant.storage.file_sandbox.get_thread_id", return_value=""):
                with pytest.raises(ValueError, match="requires user_id"):
                    get_sandbox()


# =============================================================================
# Tool Function Tests (with permission mocking)
# =============================================================================

class TestFileTools:
    """Test file tool functions."""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create a temporary root for testing."""
        root = tmp_path / "files"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @pytest.fixture
    def mock_sandbox(self, temp_root):
        """Mock get_sandbox to return temp_root sandbox."""
        sandbox = FileSandbox(
            root=temp_root,
            allowed_extensions={".txt", ".md", ".json"},
            max_file_size_mb=10
        )

        # Set up group context and mock permission check
        from executive_assistant.storage.group_storage import set_group_id
        set_group_id("test_group")

        with patch("executive_assistant.storage.file_sandbox.get_sandbox", return_value=sandbox):
            # Mock the permission check to bypass group storage requirements
            with patch("executive_assistant.storage.group_storage._check_permission_async"):
                yield sandbox

        # Clean up
        set_group_id("")

    def test_read_file_not_found(self, mock_sandbox):
        """Test reading a non-existent file."""
        from executive_assistant.storage.file_sandbox import read_file

        result = read_file.invoke({"file_path": "nonexistent.txt"})
        assert "File not found" in result

    def test_read_file_success(self, mock_sandbox):
        """Test reading an existing file."""
        from executive_assistant.storage.file_sandbox import read_file

        # Create test file
        test_file = mock_sandbox.root / "test.txt"
        test_file.write_text("Hello, world!", encoding="utf-8")

        result = read_file.invoke({"file_path": "test.txt"})
        assert result == "Hello, world!"

    def test_write_file_success(self, mock_sandbox):
        """Test writing a file."""
        from executive_assistant.storage.file_sandbox import write_file

        result = write_file.invoke({"file_path": "test.txt", "content": "Test content"})
        assert "File written" in result or "success" in result.lower()

        # Verify file was created
        test_file = mock_sandbox.root / "test.txt"
        assert test_file.exists()

    def test_write_file_size_limit(self, mock_sandbox):
        """Test writing a file that exceeds size limit."""
        from executive_assistant.storage.file_sandbox import write_file

        # Create sandbox with very small limit
        small_sandbox = FileSandbox(
            root=mock_sandbox.root,
            allowed_extensions={".txt"},
            max_file_size_mb=1  # Use 1 MB, but we'll override max_bytes
        )
        # Directly set max_bytes to 0 to force size validation failure
        small_sandbox.max_bytes = 0

        with patch("executive_assistant.storage.file_sandbox.get_sandbox", return_value=small_sandbox):
            # Also mock permission check for this inner patch
            with patch("executive_assistant.storage.group_storage._check_permission_async"):
                result = write_file.invoke({"file_path": "test.txt", "content": "x" * 1000})
                assert "Security error" in result or "exceeds limit" in result or "Error" in result

    def test_write_file_extension_blocked(self, mock_sandbox):
        """Test writing a file with blocked extension."""
        from executive_assistant.storage.file_sandbox import write_file

        result = write_file.invoke({"file_path": "test.exe", "content": "content"})
        assert "Security error" in result or "not allowed" in result or "Error" in result

    def test_list_files(self, mock_sandbox):
        """Test listing files."""
        from executive_assistant.storage.file_sandbox import list_files

        # Create test files and directories
        (mock_sandbox.root / "file1.txt").write_text("content1")
        (mock_sandbox.root / "file2.md").write_text("content2")
        (mock_sandbox.root / "subdir").mkdir()

        result = list_files.invoke({"path": "."})
        assert "file1.txt" in result or "file1" in result
        assert "file2.md" in result or "file2" in result

    def test_list_files_recursive(self, mock_sandbox):
        """Test listing files recursively."""
        from executive_assistant.storage.file_sandbox import list_files

        # Create nested structure
        (mock_sandbox.root / "level1").mkdir()
        (mock_sandbox.root / "level1" / "level2").mkdir()
        (mock_sandbox.root / "level1" / "level2" / "deep.txt").write_text("deep")

        result = list_files.invoke({"path": ".", "recursive": True})
        assert "deep" in result or "level1" in result


# =============================================================================
# Security Tests
# =============================================================================

class TestSecurity:
    """Test security features of FileSandbox."""

    def test_path_traversal_with_double_dots(self, tmp_path):
        """Test that .. traversal is blocked."""
        sandbox = FileSandbox(root=tmp_path / "safe")
        sandbox.root.mkdir(parents=True, exist_ok=True)

        with pytest.raises(SecurityError):
            sandbox._validate_path("../../../etc/passwd")

    def test_path_traversal_absolute_path(self, tmp_path):
        """Test that absolute paths outside sandbox are blocked."""
        sandbox = FileSandbox(root=tmp_path / "safe")
        sandbox.root.mkdir(parents=True, exist_ok=True)

        with pytest.raises(SecurityError):
            sandbox._validate_path("/etc/passwd")

    def test_path_traversal_symlink(self, tmp_path):
        """Test that symlinks outside sandbox are handled."""
        sandbox = FileSandbox(root=tmp_path / "safe")
        sandbox.root.mkdir(parents=True, exist_ok=True)

        # Create a symlink outside sandbox
        outside = tmp_path / "outside"
        outside.mkdir()
        link = sandbox.root / "link"
        try:
            link.symlink_to(outside)
        except OSError:
            # Symlinks may not be supported on this system
            return

        # Reading the link should fail validation
        with pytest.raises(SecurityError):
            sandbox._validate_path("link/../etc/passwd")
