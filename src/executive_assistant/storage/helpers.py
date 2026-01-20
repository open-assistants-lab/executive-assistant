"""
Helper functions for identity management and data merging.

This module provides utilities for:
- Converting thread_id to user_id
- Merging user data during identity consolidation
"""

import re
import json
import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4

from executive_assistant.config.settings import settings


def sanitize_thread_id_to_user_id(thread_id: str) -> str:
    """
    Convert thread_id to anonymous user_id.

    Examples:
        "telegram:123456789" → "anon_telegram_123456789"
        "email:user@example.com" → "anon_email_user_example_com"
        "http:session-abc-123" → "anon_http_session_abc_123"

    Args:
        thread_id: Thread identifier in format "channel:identifier"

    Returns:
        Anonymous user_id string starting with "anon_"

    Raises:
        ValueError: If thread_id format is invalid
    """
    # Extract channel and identifier
    parts = thread_id.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid thread_id format: {thread_id}")

    channel, identifier = parts

    # Sanitize identifier for use in user_id
    # Replace special chars with underscores
    safe_identifier = re.sub(r'[^a-zA-Z0-9-]', '_', identifier)

    return f"anon_{channel}_{safe_identifier}"


def generate_persistent_user_id() -> str:
    """
    Generate a new persistent user_id.

    Returns:
        User ID string starting with "user_" followed by UUID4
    """
    return f"user_{uuid4()}"


def get_user_storage_path(user_id: str) -> Path:
    """
    Get storage base path for a user_id.

    Args:
        user_id: User identifier (anon_* or user_*)

    Returns:
        Path to user storage directory (data/users/{user_id}/)
    """
    user_path = settings.USERS_ROOT / user_id
    user_path.mkdir(parents=True, exist_ok=True)
    return user_path


def merge_user_data(
    source_user_id: str,
    target_user_id: str,
    source_thread_id: str | None = None
) -> dict[str, list[str]]:
    """
    Merge data from source_user into target_user.

    Moves all data (files, db, vs, mem, meta.json) from source path to target path.
    Handles conflicts by renaming with source identifier.

    Args:
        source_user_id: Source user ID to merge from (e.g., "anon_telegram_123456")
        target_user_id: Target user ID to merge into (e.g., "user_abc123")
        source_thread_id: Optional thread ID for conflict naming (e.g., "telegram:123456")

    Returns:
        Dictionary with lists of moved items:
        {
            "files_moved": ["notes.txt", "report.pdf"],
            "dbs_moved": ["timesheets.sqlite"],
            "vs_moved": ["knowledge", "docs"],
            "conflicts_renamed": ["telegram_123456_notes.txt"]
        }
    """
    source_path = get_user_storage_path(source_user_id)
    target_path = get_user_storage_path(target_user_id)

    result = {
        "files_moved": [],
        "dbs_moved": [],
        "vs_moved": [],
        "conflicts_renamed": []
    }

    # Safe source identifier for renaming conflicts
    safe_source = source_user_id.replace(":", "_")
    if source_thread_id:
        safe_source = source_thread_id.replace(":", "_")

    # Merge meta.json first (special handling - merge JSON content)
    source_meta = source_path / "meta.json"
    target_meta = target_path / "meta.json"

    if source_meta.exists():
        if target_meta.exists():
            # Merge JSON content
            merge_meta_json(source_meta, target_meta, source_id=safe_source)
        else:
            shutil.copy2(source_meta, target_meta)
        result["files_moved"].append("meta.json")

    # Merge each subdirectory
    for subdir in ["files", "db", "vs", "mem"]:
        source_subdir = source_path / subdir
        target_subdir = target_path / subdir

        if not source_subdir.exists():
            continue

        # Create target subdirectory if needed
        target_subdir.mkdir(parents=True, exist_ok=True)

        # Move contents
        for item in source_subdir.iterdir():
            dest = target_subdir / item.name

            # Handle conflict
            if dest.exists():
                # Rename with source identifier
                new_name = f"{safe_source}_{item.name}"
                new_dest = target_subdir / new_name
                shutil.move(str(item), str(new_dest))
                result["conflicts_renamed"].append(f"{subdir}/{new_name}")
            else:
                shutil.move(str(item), str(dest))

            if subdir == "files":
                result["files_moved"].append(item.name)
            elif subdir == "db":
                result["dbs_moved"].append(item.name)
            elif subdir == "vs":
                result["vs_moved"].append(item.name)

    # Remove old empty source path
    try:
        source_path.rmdir()
    except OSError:
        # Directory not empty, keep it (shouldn't happen if all moves succeeded)
        pass

    return result


def merge_meta_json(
    source_meta: Path,
    target_meta: Path,
    source_id: str
) -> None:
    """
    Merge meta.json files, prefixing keys with source_id to avoid conflicts.

    Args:
        source_meta: Source meta.json path
        target_meta: Target meta.json path
        source_id: Source identifier for key prefixing
    """
    with open(source_meta) as f:
        source_data = json.load(f)

    with open(target_meta) as f:
        target_data = json.load(f)

    # Prefix all keys from source with source_id to avoid conflicts
    for key, value in source_data.items():
        prefixed_key = f"{source_id}_{key}"
        target_data[prefixed_key] = value

    # Write merged data
    with open(target_meta, "w") as f:
        json.dump(target_data, f, indent=2)

    # Remove source file after merge
    source_meta.unlink()


def create_identity_if_not_exists(
    thread_id: str,
    identity_id: str,
    channel: str,
    conn
) -> bool:
    """
    Create identity record if it doesn't exist.

    Args:
        thread_id: Thread identifier
        identity_id: Auto-generated identity ID (anon_*)
        channel: Channel type ('telegram', 'email', 'http')
        conn: PostgreSQL connection

    Returns:
        True if created, False if already existed
    """
    try:
        conn.execute("""
            INSERT INTO identities (identity_id, thread_id, channel)
            VALUES (?, ?, ?)
            ON CONFLICT (thread_id) DO NOTHING
        """, (identity_id, thread_id, channel))
        return True
    except Exception as e:
        # Likely already exists
        return False


def get_identity_by_thread_id(
    thread_id: str,
    conn
) -> dict | None:
    """
    Get identity by thread_id.

    Args:
        thread_id: Thread identifier
        conn: PostgreSQL connection

    Returns:
        Identity dict or None if not found
    """
    result = conn.execute("""
        SELECT * FROM identities WHERE thread_id = ?
    """, (thread_id,)).fetchone()

    return dict(result) if result else None


def get_persistent_user_id(thread_id: str, conn) -> str | None:
    """
    Get persistent user_id for a thread_id.

    Returns persistent_user_id if verified, otherwise returns identity_id.

    Args:
        thread_id: Thread identifier
        conn: PostgreSQL connection

    Returns:
        user_id string or None if not found
    """
    identity = get_identity_by_thread_id(thread_id, conn)
    if not identity:
        return None

    # Return persistent_user_id if verified, else identity_id (anon_*)
    return identity.get("persistent_user_id") or identity.get("identity_id")
