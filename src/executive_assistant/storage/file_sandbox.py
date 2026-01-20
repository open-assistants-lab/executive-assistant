"""Secure file operations within a group sandbox."""

import os
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from executive_assistant.config.settings import settings
from executive_assistant.storage.meta_registry import (
    record_file_written,
    record_file_moved,
    record_files_removed_by_prefix,
    record_folder_renamed,
)
from executive_assistant.storage.group_storage import (
    get_workspace_id,
    require_permission,
)


# Context variable for thread_id - set by channels when processing messages
# This provides true thread isolation via Python's contextvars mechanism
_thread_id: ContextVar[str | None] = ContextVar("_thread_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("_user_id", default=None)

# Thread-local fallback for thread-pool execution where ContextVar may not propagate
# Keys are thread IDs (int), values are thread_id strings (str)
_thread_local_fallback: dict[int, str] = {}
_user_local_fallback: dict[int, str] = {}
_thread_local_lock = threading.Lock()


def set_thread_id(thread_id: str) -> None:
    """Set the thread_id for the current context.

    Stores in both ContextVar (for async propagation) and thread-local dict
    (for thread-pool execution fallback).
    """
    _thread_id.set(thread_id)
    # Also store in thread-local fallback
    thread_id_int = threading.get_ident()
    with _thread_local_lock:
        _thread_local_fallback[thread_id_int] = thread_id


def set_user_id(user_id: str) -> None:
    """Set the user_id for the current context."""
    _user_id.set(user_id)
    thread_id_int = threading.get_ident()
    with _thread_local_lock:
        _user_local_fallback[thread_id_int] = user_id


def get_thread_id() -> str | None:
    """Get the thread_id for the current context.

    Uses ContextVar which provides automatic propagation across async tasks
    and thread pools, ensuring proper isolation between concurrent requests.

    Falls back to thread-local dict if ContextVar is empty (can happen in
    thread-pool execution where ContextVar doesn't propagate).
    """
    # Try ContextVar first (async-safe)
    ctx_val = _thread_id.get()
    if ctx_val:
        return ctx_val

    # Fallback: check thread-local dict
    thread_id_int = threading.get_ident()
    with _thread_local_lock:
        return _thread_local_fallback.get(thread_id_int)


def get_user_id() -> str | None:
    """Get the user_id for the current context."""
    ctx_val = _user_id.get()
    if ctx_val:
        return ctx_val

    thread_id_int = threading.get_ident()
    with _thread_local_lock:
        return _user_local_fallback.get(thread_id_int)


def clear_thread_id() -> None:
    """Clear the thread_id from the current context."""
    try:
        _thread_id.set(None)
    except Exception:
        pass
    # Also clear from thread-local fallback
    thread_id_int = threading.get_ident()
    with _thread_local_lock:
        _thread_local_fallback.pop(thread_id_int, None)


def clear_user_id() -> None:
    """Clear the user_id from the current context."""
    try:
        _user_id.set(None)
    except Exception:
        pass
    thread_id_int = threading.get_ident()
    with _thread_local_lock:
        _user_local_fallback.pop(thread_id_int, None)


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
        root: Path,
        allowed_extensions: set[str] | None = None,
        max_file_size_mb: int | None = None,
    ) -> None:
        """
        Initialize FileSandbox with a required root directory.

        Args:
            root: Root directory for the sandbox (required).
            allowed_extensions: Set of allowed file extensions.
            max_file_size_mb: Maximum file size in megabytes.
        """
        self.root = Path(root).resolve()
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

        # Check file extension
        # - Skip if allow_directories is True
        # - Check if file exists AND is a file
        # - OR if file doesn't exist (new file), check extension from path
        should_check_extension = not allow_directories and (
            requested.is_file() or not requested.exists()
        )

        if should_check_extension:
            if requested.suffix.lower() not in self.allowed_extensions:
                allowed = ", ".join(sorted(self.allowed_extensions))
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


# No global sandbox - must provide context
_sandbox = None


def get_sandbox(user_id: str | None = None) -> FileSandbox:
    """
    Get a sandbox instance scoped to user_id, group_id, or thread_id from context.

    Priority:
    1. user_id if provided (explicit parameter)
    2. user_id from context (individual mode)
    3. group_id from context (team mode)
    4. thread_id from context (legacy fallback)

    Args:
        user_id: Optional user ID for sandbox separation.

    Returns:
        A FileSandbox instance scoped to the user/thread/group.

    Raises:
        ValueError: If no user_id, group_id, or thread_id context is available.
    """
    # 1. Explicit user_id parameter
    if user_id:
        user_path = settings.get_user_files_path(user_id)
        user_path.mkdir(parents=True, exist_ok=True)
        return FileSandbox(root=user_path)

    # 2. user_id from context (individual mode)
    from executive_assistant.storage.group_storage import get_user_id
    user_id_val = get_user_id()
    if user_id_val:
        user_path = settings.get_user_files_path(user_id_val)
        user_path.mkdir(parents=True, exist_ok=True)
        return FileSandbox(root=user_path)

    # 3. group_id from context (team mode)
    group_id_val = get_workspace_id()
    if group_id_val:
        group_path = settings.get_group_files_path(group_id_val)
        group_path.mkdir(parents=True, exist_ok=True)
        return FileSandbox(root=group_path)

    # 4. thread_id from context (convert to user_id)
    # This ensures all storage is user-based, not thread-based
    thread_id_val = get_thread_id()
    if thread_id_val:
        # Convert thread_id to user_id (anon_* format)
        from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
        user_id_from_thread = sanitize_thread_id_to_user_id(thread_id_val)
        user_path = settings.get_user_files_path(user_id_from_thread)
        user_path.mkdir(parents=True, exist_ok=True)
        return FileSandbox(root=user_path)

    raise ValueError(
        "FileSandbox requires user_id, group_id, or thread_id context. "
        "Call with user_id or ensure context is set."
    )


def get_shared_sandbox() -> FileSandbox:
    """
    Get a sandbox instance for shared organization-wide file storage.

    Returns:
        A FileSandbox instance scoped to data/shared/files.

    Note:
        Shared storage is accessible by all users but writes may be
        restricted based on permissions.
    """
    shared_path = settings.get_shared_files_path()
    shared_path.mkdir(parents=True, exist_ok=True)
    return FileSandbox(root=shared_path)


def _get_sandbox_with_scope(scope: Literal["context", "shared"] = "context") -> FileSandbox:
    """
    Get sandbox based on scope.

    Args:
        scope: "context" (default) uses group_id/thread_id from context,
               "shared" uses organization-wide shared storage.

    Returns:
        FileSandbox instance for the requested scope.
    """
    if scope == "shared":
        return get_shared_sandbox()
    elif scope == "context":
        return get_sandbox()
    else:
        raise ValueError(f"Invalid scope: {scope}. Must be 'context' or 'shared'.")


@tool
@require_permission("read")
def read_file(file_path: str, scope: Literal["context", "shared"] = "context") -> str:
    """Read file contents as text. [Files]

    USE THIS WHEN: You need to read a specific file's contents (reports, notes, configurations).

    Args:
        file_path: Path relative to files directory.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        File contents as string.
    """
    sandbox = _get_sandbox_with_scope(scope)
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
@require_permission("write")
def write_file(file_path: str, content: str, scope: Literal["context", "shared"] = "context") -> str:
    """Write content to a file (creates or overwrites). [Files]

    USE THIS WHEN: Saving reports, exporting analysis results, storing reference materials.

    Args:
        file_path: Path relative to files directory.
        content: Text content to write.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message with file path.
    """
    sandbox = _get_sandbox_with_scope(scope)
    try:
        sandbox._validate_size(content)
        validated_path = sandbox._validate_path(file_path)
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        validated_path.write_text(content, encoding="utf-8")
        # Only record metadata for context-scoped files
        if scope == "context":
            record_file_written(get_thread_id(), file_path)
        return f"File written: {file_path} ({len(content)} bytes)"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def file_write(file_path: str, content: str) -> str:
    """Legacy alias for write_file (kept for backward compatibility)."""
    return write_file(file_path, content)


@tool
@require_permission("read")
def list_files(directory: str = "", recursive: bool = False, scope: Literal["context", "shared"] = "context") -> str:
    """Browse directory structure (file/folder names only). [Files]

    USE THIS WHEN: Exploring folders, seeing what's available, verifying file locations.

    For pattern search: glob_files. For content search: grep_files.

    Args:
        directory: Subdirectory to list (empty for root).
        recursive: List all files recursively if True.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        List of files and folders.
    """
    sandbox = _get_sandbox_with_scope(scope)
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
@require_permission("write")
def create_folder(folder_path: str, scope: Literal["context", "shared"] = "context") -> str:
    """
    Create a new folder in the files directory.

    Args:
        folder_path: Path for the new folder (can be nested like "docs/work").
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message or error description.

    Examples:
        >>> create_folder("documents")
        "Folder created: documents/"
        >>> create_folder("projects/2024")
        "Folder created: projects/2024/"
    """
    sandbox = _get_sandbox_with_scope(scope)
    try:
        validated_path = sandbox._validate_directory_path(folder_path)
        validated_path.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {folder_path}/"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error creating folder: {e}"


@tool
@require_permission("write")
def delete_folder(folder_path: str, scope: Literal["context", "shared"] = "context") -> str:
    """
    Delete a folder and all its contents.

    Args:
        folder_path: Path to the folder to delete.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message or error description.

    Examples:
        >>> delete_folder("old_folder")
        "Folder deleted: old_folder/"
    """
    sandbox = _get_sandbox_with_scope(scope)
    try:
        validated_path = sandbox._validate_directory_path(folder_path)

        if not validated_path.exists():
            return f"Folder not found: {folder_path}"

        if not validated_path.is_dir():
            return f"Not a folder: {folder_path}"

        import shutil
        shutil.rmtree(validated_path)
        # Only record metadata for context-scoped operations
        if scope == "context":
            record_files_removed_by_prefix(get_thread_id(), folder_path)
        return f"Folder deleted: {folder_path}/"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error deleting folder: {e}"


@tool
@require_permission("write")
def rename_folder(old_path: str, new_path: str, scope: Literal["context", "shared"] = "context") -> str:
    """
    Rename or move a folder.

    Args:
        old_path: Current folder path.
        new_path: New folder path.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message or error description.

    Examples:
        >>> rename_folder("old_folder", "new_folder")
        "Folder renamed: old_folder/ -> new_folder/"
        >>> rename_folder("docs", "documents/archive")
        "Folder renamed: docs/ -> documents/archive/"
    """
    sandbox = _get_sandbox_with_scope(scope)
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
        # Only record metadata for context-scoped operations
        if scope == "context":
            record_folder_renamed(get_thread_id(), old_path, new_path)
        return f"Folder renamed: {old_path}/ -> {new_path}/"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error renaming folder: {e}"


@tool
@require_permission("write")
def move_file(source: str, destination: str, scope: Literal["context", "shared"] = "context") -> str:
    """
    Move or rename a file.

    Args:
        source: Current file path.
        destination: New file path.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage (admin-only writes).

    Returns:
        Success message or error description.

    Examples:
        >>> move_file("old.txt", "new.txt")
        "File moved: old.txt -> new.txt"
        >>> move_file("file.txt", "docs/file.txt")
        "File moved: file.txt -> docs/file.txt"
    """
    sandbox = _get_sandbox_with_scope(scope)
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
        # Only record metadata for context-scoped operations
        if scope == "context":
            record_file_moved(get_thread_id(), source, destination)
        return f"File moved: {source} -> {destination}"
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error moving file: {e}"


@tool
@require_permission("read")
def glob_files(pattern: str, directory: str = "", scope: Literal["context", "shared"] = "context") -> str:
    """Find files by name pattern or extension. [Files]

    USE THIS WHEN: Finding files of a specific type (*.csv, *.json) or matching a name pattern.

    For browsing: list_files. For content search: grep_files.

    Args:
        pattern: Glob pattern (*.py, **/*.json, data/**/*.csv).
        directory: Base directory to search (empty for root).
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        List of matching files with sizes and timestamps.
    """
    import glob as stdlib_glob
    from datetime import datetime

    sandbox = _get_sandbox_with_scope(scope)
    try:
        base_path = sandbox.root / directory if directory else sandbox.root

        if not base_path.exists():
            return f"Directory not found: {directory}"

        if not base_path.is_dir():
            return f"Not a directory: {directory}"

        # Use glob to find matching files
        search_pattern = str(base_path / pattern)
        matches = sorted(stdlib_glob.glob(search_pattern, recursive=True))

        if not matches:
            return f"No files found matching pattern: {pattern}"

        # Build result with metadata
        from pathlib import Path as StdPath
        results = []
        for match in matches:
            p = StdPath(match)
            if p.is_file():
                # Get relative path from sandbox root
                rel_path = p.relative_to(sandbox.root)
                size = p.stat().st_size
                mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                results.append(f"- {rel_path} ({size} bytes, {mtime})")

        return f"Found {len(results)} file(s) matching '{pattern}':\n" + "\n".join(results)
    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error globbing files: {e}"


@tool
@require_permission("read")
def grep_files(
    pattern: str,
    directory: str = "",
    output_mode: str = "content",
    context_lines: int = 2,
    ignore_case: bool = False,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """Search INSIDE file contents (like Unix grep). [Files]

    USE THIS WHEN: Finding specific text/patterns WITHIN files (e.g., which files contain "TODO", function definitions).

    For browsing: list_files. For filename search: glob_files.

    Args:
        pattern: Regular expression to search for.
        directory: Directory to search (empty for root).
        output_mode: "files" (list), "content" (show matches), "count" (per-file totals).
        context_lines: Context lines before/after matches.
        ignore_case: Case-insensitive search.
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        Search results in specified format.
    """
    import re
    from pathlib import Path as StdPath

    sandbox = _get_sandbox_with_scope(scope)
    try:
        base_path = sandbox.root / directory if directory else sandbox.root

        if not base_path.exists():
            return f"Directory not found: {directory}"

        if not base_path.is_dir():
            return f"Not a directory: {directory}"

        # Compile regex pattern
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        # Search through all files
        matches = {}
        for file_path in base_path.rglob("*"):
            if file_path.is_file():
                # Check file extension
                if file_path.suffix.lower() not in sandbox.allowed_extensions:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines = content.splitlines()

                    file_matches = []
                    for line_num, line in enumerate(lines, start=1):
                        if regex.search(line):
                            file_matches.append((line_num, line))

                    if file_matches:
                        rel_path = file_path.relative_to(sandbox.root)
                        matches[rel_path] = file_matches
                except (UnicodeDecodeError, PermissionError):
                    # Skip files that can't be read as text
                    continue

        if not matches:
            return f"No matches found for pattern: {pattern}"

        # Format output based on mode
        if output_mode == "files":
            result = f"Found '{pattern}' in {len(matches)} file(s):\n"
            result += "\n".join(f"- {p}" for p in sorted(matches.keys()))
            return result

        elif output_mode == "count":
            result = f"Found '{pattern}' in {len(matches)} file(s):\n"
            sorted_matches = sorted(matches.items(), key=lambda x: -len(x[1]))
            for path, file_matches in sorted_matches:
                count = len(file_matches)
                suffix = "match" if count == 1 else "matches"
                result += f"- {path}: {count} {suffix}\n"
            return result.rstrip()

        else:  # content mode
            result = f"Found '{pattern}' in {len(matches)} file(s):\n\n"
            for path in sorted(matches.keys()):
                result += f"{path}:\n"
                file_matches = matches[path]

                # Show matches with context
                for line_num, line in file_matches:
                    # Add context lines before
                    start = max(0, line_num - context_lines - 1)
                    end = min(len(file_matches), file_matches.index((line_num, line)) + 1)
                    # Get all lines for this file
                    try:
                        full_content = (sandbox.root / path).read_text(encoding="utf-8")
                        all_lines = full_content.splitlines()
                    except:
                        continue

                    for i in range(max(0, line_num - context_lines - 1),
                                 min(len(all_lines), line_num + context_lines)):
                        prefix = "  " if i != line_num - 1 else ">>"
                        result += f"{prefix} {i+1}: {all_lines[i]}\n"
                    result += "\n"
            return result.rstrip()

    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error grepping files: {e}"


@tool
@require_permission("read")
def find_files_fuzzy(
    query: str,
    directory: str = "",
    recursive: bool = True,
    limit: int = 10,
    score_cutoff: int = 70,
    scope: Literal["context", "shared"] = "context",
) -> str:
    """
    Find files by fuzzy matching the filename/path (tolerates typos and partial matches).

    USE THIS WHEN: You want to find files but aren't sure of the exact name,
    or want to find similar files even with typos. Uses RapidFuzz for intelligent matching.

    For browsing a folder, use list_files instead.
    For finding files by pattern, use glob_files instead.
    For searching inside file contents, use grep_files instead.

    Args:
        query: Search query for filename/path (fuzzy matching).
               Examples: "config", "main", "test_utils", "README"
        directory: Base directory to search in (empty for sandbox root).
        recursive: If True, search all subdirectories.
        limit: Maximum number of results to return (default: 10).
        score_cutoff: Minimum similarity score (0-100). Default 70 = 70% similar.
                     Lower this value to get more results (but less accurate).
        scope: "context" (default) for group/thread-scoped storage,
               "shared" for organization-wide shared storage.

    Returns:
        List of matching files ranked by similarity score.

    Examples:
        >>> find_files_fuzzy("config")
        "Found 3 files matching 'config':
        - config.py (95%)
        - config.yaml (89%)
        - old_config.json (72%)"

        >>> find_files_fuzzy("test", "src", limit=5)
        "Found 5 files matching 'test' in src:
        - test_main.py (91%)
        - test_utils.py (88%)
        ..."
    """
    from pathlib import Path as StdPath
    from rapidfuzz import process, fuzz

    sandbox = _get_sandbox_with_scope(scope)
    try:
        base_path = sandbox.root / directory if directory else sandbox.root

        if not base_path.exists():
            return f"Directory not found: {directory}"

        if not base_path.is_dir():
            return f"Not a directory: {directory}"

        # Collect all files
        if recursive:
            all_files = list(base_path.rglob("*"))
        else:
            all_files = list(base_path.glob("*"))

        # Filter to files only (not directories)
        files = [
            f.relative_to(sandbox.root)
            for f in all_files
            if f.is_file()
        ]

        if not files:
            return f"No files found in {directory or 'root'}"

        # Convert paths to strings for fuzzy matching
        file_paths = [str(f) for f in files]

        # Use RapidFuzz to find closest matches
        matches = process.extract(
            query,
            file_paths,
            scorer=fuzz.WRatio,  # Weighted ratio for good balance
            limit=limit,
        )

        # Filter by score cutoff
        filtered_matches = [
            (path, score)
            for path, score, _ in matches
            if score >= score_cutoff
        ]

        if not filtered_matches:
            return f"No files found matching '{query}' (score cutoff: {score_cutoff}%). Try lowering the score_cutoff or using a different query."

        # Format results
        result = f"Found {len(filtered_matches)} file(s) matching '{query}':\n"
        for path, score in filtered_matches:
            result += f"- {path} ({score:.0f}%)\n"

        return result.rstrip()

    except SecurityError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error in fuzzy file search: {e}"
