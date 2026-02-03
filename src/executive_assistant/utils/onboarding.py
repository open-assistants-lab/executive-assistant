"""Onboarding detection and utilities for Executive Assistant."""

import os
import re
from pathlib import Path
from typing import Literal

from executive_assistant.config import settings
from executive_assistant.storage.mem_storage import get_mem_storage
from executive_assistant.storage.instinct_storage import get_instinct_storage


# Vague request patterns that suggest new/unfamiliar users
# NOTE: These patterns are matched against lowercase messages
VAGUE_PATTERNS = [
    r"^(hi|hello|hey)\s*[.!?]*$",     # Just greeting
    r"^help\s*[.!?]*$",                # Just "help"
    r"^what can you do\s*[.!?]*$",     # Generic capability question
    r"^(i need|i want)\s{0,5}$",      # Very incomplete sentence (just "I need" or "I want" with minimal text)
]


def is_vague_request(message: str) -> bool:
    """Check if message is a vague request suggesting unfamiliarity.

    Args:
        message: User message to check

    Returns:
        True if message matches vague request patterns
    """
    if not message:
        return False

    message_lower = message.strip().lower()
    return any(re.match(pattern, message_lower) for pattern in VAGUE_PATTERNS)


def is_user_data_empty(thread_id: str) -> bool:
    """Check if user's data folder is empty (triggers onboarding).

    This is the definitive onboarding trigger:
    - Empty folder = new user OR user reset everything
    - Has data = onboarding already done

    Args:
        thread_id: Thread identifier

    Returns:
        True if user data folder is empty or doesn't exist
    """
    try:
        user_root = settings.get_thread_root(thread_id)

        # Check if user root exists
        if not user_root.exists():
            return True

        # Check for onboarding marker file (prevents re-triggering during same conversation)
        onboarding_marker = user_root / ".onboarding_in_progress"
        if onboarding_marker.exists():
            # Onboarding already in progress, don't re-trigger
            return False

        # Check for ANY data in user folder
        # Look for: databases, files, memories, instincts
        has_data = False

        # Check for TDB databases
        tdb_dir = user_root / "tdb"
        if tdb_dir.exists():
            db_files = list(tdb_dir.glob("*.sqlite"))
            if db_files:
                has_data = True

        # Check for VDB databases
        vdb_dir = user_root / "vdb"
        if vdb_dir.exists():
            vdb_dbs = list(vdb_dir.glob("*"))
            if vdb_dbs:
                has_data = True

        # Check for files
        files_dir = user_root / "files"
        if files_dir.exists():
            files = list(files_dir.rglob("*"))
            # Ignore hidden files
            files = [f for f in files if not f.name.startswith(".")]
            if files:
                has_data = True

        # Check for memories
        try:
            mem_storage = get_mem_storage()
            memories = mem_storage.list_memories(thread_id)
            if memories and len(memories) > 0:
                has_data = True
        except:
            pass

        # Check for instincts
        try:
            instinct_storage = get_instinct_storage()
            instincts = instinct_storage.list_instincts(thread_id)
            if instincts and len(instincts) > 0:
                has_data = True
        except:
            pass

        return not has_data

    except Exception:
        # If we can't check, assume empty to be safe
        return True


def mark_onboarding_started(thread_id: str) -> None:
    """Mark onboarding as in-progress (prevents re-triggering during conversation).

    Args:
        thread_id: Thread identifier
    """
    try:
        user_root = settings.get_thread_root(thread_id)
        marker = user_root / ".onboarding_in_progress"
        marker.touch()
    except Exception:
        # Fail silently
        pass


def mark_onboarding_complete(thread_id: str) -> None:
    """Mark onboarding as complete and remove in-progress marker.

    Args:
        thread_id: Thread identifier
    """
    try:
        user_root = settings.get_thread_root(thread_id)
        marker = user_root / ".onboarding_in_progress"

        # Remove marker if exists
        if marker.exists():
            marker.unlink()

        # Also create a completion memory
        try:
            from executive_assistant.tools.mem_tools import create_memory

            create_memory(
                content="Onboarding completed - user introduced and first setup complete",
                memory_type="system",
                key="onboarding_complete",
                confidence=1.0,
            )
        except Exception:
            # Memory creation is optional
            pass

    except Exception:
        # Fail silently
        pass


def should_show_onboarding(thread_id: str) -> bool:
    """Detect if user needs onboarding.

    Args:
        thread_id: Thread identifier to check

    Returns:
        True if onboarding should be shown
    """
    try:
        # Check if user data folder is empty
        return is_user_data_empty(thread_id)
    except Exception:
        # If we can't check, assume onboarding not needed to avoid errors
        return False


def has_completed_onboarding(thread_id: str) -> bool:
    """Check if user has already completed onboarding.

    Args:
        thread_id: Thread identifier to check

    Returns:
        True if onboarding completion marker exists
    """
    try:
        mem_storage = get_mem_storage()
        memories = mem_storage.list_memories(thread_id) if mem_storage else []

        if not memories:
            return False

        # Check for onboarding completion marker
        for memory in memories:
            if memory.get("key") == "onboarding_complete":
                return True

        return False

    except Exception:
        return False


def extract_user_profile(memories: list) -> dict:
    """Extract user profile from stored memories.

    Args:
        memories: List of memory dictionaries

    Returns:
        Dict with keys: role, expertise, communication_style, etc.
    """
    profile = {
        "role": None,
        "expertise": None,
        "communication_style": None,
        "preferences": [],
    }

    if not memories:
        return profile

    for memory in memories:
        key = memory.get("key", "")
        content = memory.get("content", "")

        if "role" in key.lower():
            profile["role"] = content
        elif "expertise" in key.lower():
            profile["expertise"] = content
        elif "style" in key.lower() or "communication" in key.lower():
            profile["communication_style"] = content
        elif "preference" in key.lower():
            profile["preferences"].append(content)

    return profile


def get_onboarding_stage(thread_id: str) -> Literal["new", "partial", "complete"]:
    """Get onboarding stage for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        "new" - No onboarding done, "partial" - Some info gathered, "complete" - Finished
    """
    if has_completed_onboarding(thread_id):
        return "complete"

    try:
        mem_storage = get_mem_storage()
        memories = mem_storage.list_memories(thread_id) if mem_storage else []

        if not memories or len(memories) < 3:
            return "new"

        return "partial"

    except Exception:
        return "new"
