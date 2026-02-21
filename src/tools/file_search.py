"""File search tools for agent - glob and grep."""

import re
from collections import Counter
from pathlib import Path

from langchain_core.tools import tool

from src.app_logging import get_logger
from src.config import get_settings

logger = get_logger()


def _get_root_path(user_id: str) -> Path:
    """Get root path for user."""
    settings = get_settings()
    return Path(settings.filesystem.root_path.format(user_id=user_id))


def _resolve_path(path: str | None, user_id: str) -> Path:
    """Resolve path relative to user's root."""
    root = _get_root_path(user_id)
    if path is None:
        return root

    resolved = (root / path).resolve()

    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path outside user directory: {path}")

    return resolved


@tool
def glob_search(pattern: str = "**/*", path: str = ".", user_id: str = "default") -> str:
    """Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.txt")
        path: Directory to search in (default: current dir)
        user_id: User identifier

    Returns:
        List of matching files
    """
    try:
        root = _get_root_path(user_id)
        target = _resolve_path(path, user_id)

        if not target.exists():
            return f"Directory not found: {path}"

        matches = list(target.glob(pattern))
        matches = [m for m in matches if str(m).startswith(str(root))]

        if not matches:
            return f"No files matching {pattern} in {path}"

        matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        results = []
        for m in matches:
            rel_path = m.relative_to(root)
            size = m.stat().st_size if m.is_file() else 0
            results.append(f"{rel_path} ({size} bytes)")

        return "\n".join(["", *results, f"\n{len(results)} files found"])
    except Exception as e:
        logger.error("glob_search.error", {"pattern": pattern, "error": str(e)})
        return f"Error: {e}"


@tool
def grep_search(
    pattern: str,
    path: str = ".",
    include: str | None = None,
    count: bool = False,
    user_id: str = "default",
) -> str:
    """Search file contents using regex.

    Args:
        pattern: Regex pattern to search for
        path: Directory to search in (default: current dir)
        include: File pattern to filter (e.g., "*.py", "*.txt")
        count: If True, return only count of matches
        user_id: User identifier

    Returns:
        Matching lines with context
    """
    try:
        root = _get_root_path(user_id)
        target = _resolve_path(path, user_id)

        if not target.exists():
            return f"Directory not found: {path}"

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"

        matches = []
        settings = get_settings()
        max_size = getattr(settings.filesystem, "max_file_size_mb", 10) * 1024 * 1024

        for file_path in target.rglob(include or "*"):
            if not file_path.is_file():
                continue

            try:
                if file_path.stat().st_size > max_size:
                    continue
            except OSError:
                continue

            if not str(file_path).startswith(str(root)):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    rel_path = file_path.relative_to(root)
                    if count:
                        matches.append(f"{rel_path}:{line_num}")
                    else:
                        matches.append(f"{rel_path}:{line_num}: {line[:200]}")

        if not matches:
            return f"No matches for '{pattern}' in {path}"

        if count:
            file_counts = Counter(m.split(":")[0] for m in matches)
            result = [f"{k}: {v} matches" for k, v in file_counts.most_common()]
        else:
            result = matches[:100]
            if len(matches) > 100:
                result.append(f"... and {len(matches) - 100} more matches")

        return "\n".join(["", *result, ""])
    except Exception as e:
        logger.error("grep_search.error", {"pattern": pattern, "error": str(e)})
        return f"Error: {e}"
