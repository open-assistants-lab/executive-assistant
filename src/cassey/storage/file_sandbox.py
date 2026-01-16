"""Secure file operations within a workspace sandbox."""

import os
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from cassey.config.settings import settings


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
        # Use new path helper with backward compatibility fallback
        thread_path = settings.get_thread_files_path(thread_id_val)
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
def file_write(file_path: str, content: str) -> str:
    """Legacy alias for write_file (kept for backward compatibility)."""
    return write_file(file_path, content)


@tool
def list_files(directory: str = "", recursive: bool = False) -> str:
    """
    List files and folders in a directory (browse directory structure).

    USE THIS WHEN: You want to see what's in a folder, explore directory structure,
    or get an overview of available files. This shows file/folder NAMES only.

    For finding files by pattern, use glob_files instead.
    For searching file contents, use grep_files instead.

    Args:
        directory: Subdirectory to list (empty for root).
        recursive: If True, list all files recursively.

    Returns:
        List of files and directories.

    Examples:
        >>> list_files()
        "Files in files: notes.txt, data/"

        >>> list_files("docs")
        "Files in docs/: file1.txt, file2.md, subdir/"

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


@tool
def glob_files(pattern: str, directory: str = "") -> str:
    """
    Find files by name pattern or extension (like "find . -name").

    USE THIS WHEN: You need to find files of a specific type (e.g., "*.py", "*.json"),
    or find files matching a name pattern. Shows file sizes and timestamps.

    For browsing a folder, use list_files instead.
    For searching inside file contents, use grep_files instead.

    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.json", "data/**/*.csv").
        directory: Base directory to search in (empty for sandbox root).

    Returns:
        List of matching files with sizes and modified times.

    Examples:
        >>> glob_files("*.py")
        "Found 3 Python files:
        - main.py (1024 bytes, 2024-01-15 10:30)
        - utils.py (512 bytes, 2024-01-14 15:20)
        - config.py (256 bytes, 2024-01-13 09:00)"

        >>> glob_files("**/*.json", "docs")
        "Found 2 JSON files:
        - docs/data/schema.json (2048 bytes)
        - docs/api/endpoints.json (1024 bytes)"
    """
    import glob as stdlib_glob
    from datetime import datetime

    sandbox = get_sandbox()
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
def grep_files(
    pattern: str,
    directory: str = "",
    output_mode: str = "content",
    context_lines: int = 2,
    ignore_case: bool = False
) -> str:
    """
    Search INSIDE file contents (like Unix grep command).

    USE THIS WHEN: You need to find specific text or patterns WITHIN files,
    e.g., find which files contain "TODO", search for function names, find API keys.
    This searches file CONTENTS, not filenames.

    For browsing a folder, use list_files instead.
    For finding files by name/type, use glob_files instead.
    For fuzzy filename search, use find_files_fuzzy instead.

    Args:
        pattern: Regular expression pattern to search for.
        directory: Directory to search in (empty for sandbox root).
        output_mode: Output format:
            - "files": Only list matching files
            - "content": Show matching lines with context (default)
            - "count": Show match counts per file
        context_lines: Number of context lines before/after matches (for content mode).
        ignore_case: Case-insensitive search.

    Returns:
        Search results in the specified format.

    Examples:
        >>> grep_files("TODO", output_mode="files")
        "Found 'TODO' in 2 files:
        - main.py
        - utils.py"

        >>> grep_files("import.*os", output_mode="content", context_lines=1)
        "Found 'import.*os' in 2 files:
        main.py:
        3: import os
        4: import sys
        ..."

        >>> grep_files("error", output_mode="count", ignore_case=True)
        "Found 'error' (case-insensitive) in 3 files:
        - main.py: 5 matches
        - utils.py: 2 matches
        - config.py: 1 match"
    """
    import re
    from pathlib import Path as StdPath

    sandbox = get_sandbox()
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
def find_files_fuzzy(
    query: str,
    directory: str = "",
    recursive: bool = True,
    limit: int = 10,
    score_cutoff: int = 70,
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

    sandbox = get_sandbox()
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
