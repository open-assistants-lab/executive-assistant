"""Filesystem tools for agent - read, write, edit, list, delete files."""

from pathlib import Path

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


def _resolve_path(path: str | None, user_id: str) -> Path:
    """Resolve path relative to user's root, prevent escape."""
    settings = get_settings()
    root_path = Path(settings.filesystem.root_path.format(user_id=user_id))
    root_path = root_path.resolve()  # Make absolute

    if path is None:
        return root_path

    resolved = (root_path / path).resolve()

    # Ensure both are absolute paths for comparison
    if not resolved.is_relative_to(root_path):
        raise ValueError(f"Path outside user directory: {path}")

    return resolved


@tool
def list_files(path: str = ".", user_id: str = "default") -> str:
    """List files in a directory.

    Args:
        path: Directory path relative to user files (default: current dir)
        user_id: User identifier

    Returns:
        Formatted list of files and directories
    """
    try:
        target = _resolve_path(path, user_id)

        if not target.exists():
            return f"Directory not found: {path}"

        if not target.is_dir():
            return f"Not a directory: {path}"

        items = []
        for item in sorted(target.iterdir()):
            item_type = "DIR" if item.is_dir() else "FILE"
            size = item.stat().st_size if item.is_file() else 0
            items.append(f"{item_type:6} {size:>10} {item.name}")

        if not items:
            return f"Empty directory: {path}"

        return "\n".join(["", *items, ""])
    except Exception as e:
        logger.error("list_files.error", {"path": path, "error": str(e)}, user_id=user_id)
        return f"Error: {e}"


@tool
def read_file(path: str, offset: int = 0, limit: int = 100, user_id: str = "default") -> str:
    """Read file content.

    Args:
        path: File path relative to user files
        offset: Line number to start from (default: 0)
        limit: Maximum number of lines to read (default: 100)
        user_id: User identifier

    Returns:
        File content or error message
    """
    try:
        target = _resolve_path(path, user_id)

        if not target.exists():
            return f"File not found: {path}"

        if not target.is_file():
            return f"Not a file: {path}"

        lines = target.read_text(encoding="utf-8").splitlines()

        total = len(lines)
        lines = lines[offset : offset + limit]

        content = "\n".join(lines)
        return f"--- {path} ({offset}-{offset + len(lines)}/{total}) ---\n{content}"
    except Exception as e:
        logger.error("read_file.error", {"path": path, "error": str(e)}, user_id=user_id)
        return f"Error: {e}"


@tool
def write_file(path: str, content: str, user_id: str = "default") -> str:
    """Write content to a file (creates or overwrites).

    Args:
        path: File path relative to user files
        content: Content to write
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        target = _resolve_path(path, user_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        logger.info("write_file", {"path": str(target), "size": len(content)}, user_id=user_id)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        logger.error("write_file.error", {"path": path, "error": str(e)}, user_id=user_id)
        return f"Error: {e}"


@tool
def edit_file(path: str, old: str, new: str, user_id: str = "default") -> str:
    """Edit a file by replacing text.

    Args:
        path: File path relative to user files
        old: Text to replace
        new: Replacement text
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        target = _resolve_path(path, user_id)

        if not target.exists():
            return f"File not found: {path}"

        content = target.read_text(encoding="utf-8")

        if old not in content:
            return f"Text not found in file: {old[:50]}..."

        new_content = content.replace(old, new)
        target.write_text(new_content, encoding="utf-8")

        logger.info("edit_file", {"path": str(target)}, user_id=user_id)
        return f"Edited {path}"
    except Exception as e:
        logger.error("edit_file.error", {"path": path, "error": str(e)}, user_id=user_id)
        return f"Error: {e}"


@tool
def delete_file(path: str, user_id: str = "default") -> str:
    """Delete a file.

    NOTE: This tool requires human approval before execution.

    Args:
        path: File path relative to user files
        user_id: User identifier

    Returns:
        Success or error message
    """
    try:
        target = _resolve_path(path, user_id)

        if not target.exists():
            return f"File not found: {path}"

        if target.is_dir():
            import shutil

            shutil.rmtree(target)
        else:
            target.unlink()

        logger.info("delete_file", {"path": str(target)}, user_id=user_id)
        return f"Deleted {path}"
    except Exception as e:
        logger.error("delete_file.error", {"path": path, "error": str(e)}, user_id=user_id)
        return f"Error: {e}"
