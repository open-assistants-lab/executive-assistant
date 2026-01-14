"""Secure file operations within a workspace sandbox."""

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from cassey.config.settings import settings


# Context variable for thread_id - set by channels when processing messages
_thread_id: ContextVar[str | None] = ContextVar("_thread_id", default=None)

# Fallback module-level storage for thread_id (for LangChain tool execution)
# ContextVar doesn't propagate through LangChain's tool execution
_module_thread_id: str | None = None


def set_thread_id(thread_id: str) -> None:
    """Set the thread_id for the current context."""
    global _module_thread_id
    _thread_id.set(thread_id)
    _module_thread_id = thread_id


def get_thread_id() -> str | None:
    """Get the thread_id for the current context.

    First checks the ContextVar (for direct calls), then falls back to
    the module-level variable (for LangChain tool execution).
    """
    ctx_val = _thread_id.get()
    if ctx_val:
        return ctx_val
    return _module_thread_id


def clear_thread_id() -> None:
    """Clear the thread_id from both storage mechanisms."""
    global _module_thread_id
    _module_thread_id = None
    # Reset the ContextVar by setting a new token
    try:
        _thread_id.set(None)
    except Exception:
        pass


class FileSandbox:
    """
    Secure sandbox for file operations.

    Prevents path traversal attacks and restricts file access to
    allowed extensions and size limits.

    Attributes:
        root: Root directory for file operations.
        allowed_extensions: Set of allowed file extensions.
        max_file_size_mb: Maximum file size in megabytes.
    """

    def __init__(
        self,
        root: Path | None = None,
        allowed_extensions: set[str] | None = None,
        max_file_size_mb: int | None = None,
    ) -> None:
        self.root = (root or settings.FILES_ROOT).resolve()
        self.allowed_extensions = allowed_extensions or settings.ALLOWED_FILE_EXTENSIONS
        self.max_file_size_mb = max_file_size_mb or settings.MAX_FILE_SIZE_MB
        self.max_bytes = self.max_file_size_mb * 1024 * 1024

    def _validate_path(self, path: str | Path, allow_directories: bool = False) -> Path:
        """
        Validate and resolve a path within the sandbox.

        Args:
            path: Path to validate.
            allow_directories: If True, skip extension check for directories.

        Returns:
            Resolved absolute path within the sandbox root.

        Raises:
            SecurityError: If path traversal attempt detected.
            SecurityError: If file extension not allowed.
        """
        # Resolve path relative to sandbox root, not current directory
        requested = (self.root / path).resolve()
        root = self.root.resolve()

        # Check for path traversal
        try:
            requested.relative_to(root)
        except ValueError:
            raise SecurityError(
                f"Path traversal blocked: {requested} is outside sandbox {root}"
            )

        # Check file extension (skip if it's a directory or allow_directories is True)
        if not allow_directories and requested.is_file():
            if requested.suffix.lower() not in self.allowed_extensions:
                allowed = ", ".join(self.allowed_extensions)
                raise SecurityError(
                    f"File type '{requested.suffix}' not allowed. Allowed types: {allowed}"
                )

        return requested

    def _validate_directory_path(self, path: str | Path) -> Path:
        """
        Validate and resolve a directory path within the sandbox.

        Similar to _validate_path but always allows directories.

        Args:
            path: Path to validate.

        Returns:
            Resolved absolute path within the sandbox root.
        """
        requested = (self.root / path).resolve()
        root = self.root.resolve()

        # Check for path traversal
        try:
            requested.relative_to(root)
        except ValueError:
            raise SecurityError(
                f"Path traversal blocked: {requested} is outside sandbox {root}"
            )

        return requested

    def _validate_size(self, content: str | bytes) -> None:
        """Validate content size."""
        size = len(content.encode() if isinstance(content, str) else content)
        if size > self.max_bytes:
            raise SecurityError(
                f"File size {size} bytes exceeds limit {self.max_bytes} bytes "
                f"({self.max_file_size_mb}MB)"
            )


class SecurityError(Exception):
    """Raised when a security constraint is violated."""


# Global sandbox instance
_sandbox = FileSandbox()


def get_sandbox(user_id: str | None = None) -> FileSandbox:
    """
    Get a sandbox instance, optionally user-specific or thread-specific.

    Priority:
    1. user_id if provided (for backward compatibility)
    2. thread_id from context (set by channels)
    3. global sandbox (no separation)

    Args:
        user_id: Optional user ID for sandbox separation.

    Returns:
        A FileSandbox instance scoped to the user/thread.
    """
    if user_id:
        user_path = settings.FILES_ROOT / user_id
        user_path.mkdir(parents=True, exist_ok=True)
        return FileSandbox(root=user_path)

    # Check for thread_id in context
    thread_id_val = get_thread_id()
    if thread_id_val:
        # Sanitize thread_id for use as directory name
        # Replace colons, slashes, @, and backslashes with underscores
        safe_thread_id = thread_id_val
        for char in (":", "/", "@", "\\"):
            safe_thread_id = safe_thread_id.replace(char, "_")
        thread_path = settings.FILES_ROOT / safe_thread_id
        thread_path.mkdir(parents=True, exist_ok=True)
        return FileSandbox(root=thread_path)

    return _sandbox


@tool
def read_file(file_path: str) -> str:
    """
    Read a file from the files directory.

    Args:
        file_path: Path to the file relative to files directory.

    Returns:
        File contents as string.

    Examples:
        >>> read_file("notes.txt")
        "Hello, world!"
    """
    sandbox = get_sandbox()
    try:
        validated_path = sandbox._validate_path(file_path)
        return validated_path.read_text(encoding="utf-8")
    except SecurityError as e:
        return f"Security error: {e}"
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file in the files directory.

    Args:
        file_path: Path to the file relative to files directory.
        content: Content to write.

    Returns:
        Success message or error description.

    Examples:
        >>> write_file("notes.txt", "Hello, world!")
        "File written: notes.txt"
    """
    sandbox = get_sandbox()
    try:
        sandbox._validate_size(content)
        validated_path = sandbox._validate_path(file_path)
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        validated_path.write_text(content, encoding="utf-8")
        return f"File written: {file_path} ({len(content)} bytes)"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def list_files(directory: str = "", recursive: bool = False) -> str:
    """
    List files in the files directory.

    Args:
        directory: Subdirectory to list (empty for root).
        recursive: If True, list all files recursively.

    Returns:
        List of files and directories.

    Examples:
        >>> list_files()
        "Files in files: notes.txt, data/"
        >>> list_files("docs", recursive=True)
        "Files in docs/: file1.txt\\n  subdir/file2.txt"
    """
    sandbox = get_sandbox()
    try:
        # Use the directory relative to sandbox root
        target_path = sandbox.root / directory if directory else sandbox.root

        if not target_path.exists():
            return f"Directory not found: {directory}"

        if not target_path.is_dir():
            return f"Not a directory: {directory}"

        items = []
        if recursive:
            # Recursive listing with indentation
            def list_recursive(path: Path, prefix: str = ""):
                for item in sorted(path.iterdir()):
                    if item.is_dir():
                        items.append(f"{prefix}{item.name}/")
                        list_recursive(item, prefix + "  ")
                    else:
                        items.append(f"{prefix}{item.name}")
            list_recursive(target_path)
        else:
            # Non-recursive listing
            for item in target_path.iterdir():
                if item.is_dir():
                    items.append(f"{item.name}/")
                else:
                    items.append(item.name)

        if not items:
            return f"Directory {directory or 'files'} is empty"

        return f"Files in {directory or 'files'}:\n" + "\n".join(items)
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error listing files: {e}"


@tool
def create_folder(folder_path: str) -> str:
    """
    Create a new folder in the files directory.

    Args:
        folder_path: Path for the new folder (can be nested like "docs/work").

    Returns:
        Success message or error description.

    Examples:
        >>> create_folder("documents")
        "Folder created: documents/"
        >>> create_folder("projects/2024")
        "Folder created: projects/2024/"
    """
    sandbox = get_sandbox()
    try:
        validated_path = sandbox._validate_directory_path(folder_path)
        validated_path.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {folder_path}/"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error creating folder: {e}"


@tool
def delete_folder(folder_path: str) -> str:
    """
    Delete a folder and all its contents.

    Args:
        folder_path: Path to the folder to delete.

    Returns:
        Success message or error description.

    Examples:
        >>> delete_folder("old_folder")
        "Folder deleted: old_folder/"
    """
    sandbox = get_sandbox()
    try:
        validated_path = sandbox._validate_directory_path(folder_path)

        if not validated_path.exists():
            return f"Folder not found: {folder_path}"

        if not validated_path.is_dir():
            return f"Not a folder: {folder_path}"

        import shutil
        shutil.rmtree(validated_path)
        return f"Folder deleted: {folder_path}/"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error deleting folder: {e}"


@tool
def rename_folder(old_path: str, new_path: str) -> str:
    """
    Rename or move a folder.

    Args:
        old_path: Current folder path.
        new_path: New folder path.

    Returns:
        Success message or error description.

    Examples:
        >>> rename_folder("old_folder", "new_folder")
        "Folder renamed: old_folder/ -> new_folder/"
        >>> rename_folder("docs", "documents/archive")
        "Folder renamed: docs/ -> documents/archive/"
    """
    sandbox = get_sandbox()
    try:
        old_validated = sandbox._validate_directory_path(old_path)
        new_validated = sandbox._validate_directory_path(new_path)

        if not old_validated.exists():
            return f"Source folder not found: {old_path}"

        if not old_validated.is_dir():
            return f"Source is not a folder: {old_path}"

        if new_validated.exists():
            return f"Target already exists: {new_path}"

        import shutil
        shutil.move(str(old_validated), str(new_validated))
        return f"Folder renamed: {old_path}/ -> {new_path}/"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error renaming folder: {e}"


@tool
def move_file(source: str, destination: str) -> str:
    """
    Move or rename a file.

    Args:
        source: Current file path.
        destination: New file path.

    Returns:
        Success message or error description.

    Examples:
        >>> move_file("old.txt", "new.txt")
        "File moved: old.txt -> new.txt"
        >>> move_file("file.txt", "docs/file.txt")
        "File moved: file.txt -> docs/file.txt"
    """
    sandbox = get_sandbox()
    try:
        source_validated = sandbox._validate_path(source, allow_directories=True)
        dest_validated = sandbox._validate_path(destination, allow_directories=True)

        if not source_validated.exists():
            return f"Source file not found: {source}"

        if source_validated.is_dir():
            return f"Source is a folder, use rename_folder instead: {source}"

        # Create parent directory if needed
        dest_validated.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.move(str(source_validated), str(dest_validated))
        return f"File moved: {source} -> {destination}"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error moving file: {e}"
