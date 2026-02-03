"""Migration utilities for instincts from JSON to SQLite.

This module handles the safe migration of instincts from the old JSON-based
storage (instincts.jsonl + instincts.snapshot.json) to the new SQLite-based
storage (instincts.db).

Migration Process:
1. Backup existing JSON files
2. Read current state from JSONL
3. Create SQLite database with schema
4. Migrate all instincts to SQLite
5. Verify migration success
6. Keep JSON files as backup (not deleted)
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executive_assistant.config import settings
from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def migrate_thread_to_sqlite(
    thread_id: str,
    backup: bool = True,
    verify: bool = True,
) -> dict[str, Any]:
    """
    Migrate a single thread's instincts from JSON to SQLite.

    Args:
        thread_id: Thread identifier
        backup: Whether to backup JSON files before migration
        verify: Whether to verify migration success

    Returns:
        Migration statistics
    """
    instincts_dir = settings.get_thread_instincts_dir(thread_id)
    jsonl_path = instincts_dir / "instincts.jsonl"
    snapshot_path = instincts_dir / "instincts.snapshot.json"
    db_path = instincts_dir / "instincts.db"

    # Check if migration already done
    if db_path.exists():
        return {
            "status": "already_migrated",
            "thread_id": thread_id,
            "message": "SQLite database already exists",
        }

    # Check if JSON files exist
    if not jsonl_path.exists():
        return {
            "status": "no_data",
            "thread_id": thread_id,
            "message": "No JSONL file found",
        }

    # Backup JSON files if requested
    if backup:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if jsonl_path.exists():
            shutil.copy2(jsonl_path, f"{jsonl_path}.backup_{timestamp}")
        if snapshot_path.exists():
            shutil.copy2(snapshot_path, f"{snapshot_path}.backup_{timestamp}")

    # Load instincts from JSON
    instincts = _load_instincts_from_json(jsonl_path, snapshot_path)

    # Create SQLite storage and migrate
    storage = InstinctStorageSQLite()
    migrated_count = 0
    failed_count = 0

    for instinct in instincts:
        try:
            # Create instinct in SQLite
            storage.create_instinct(
                trigger=instinct["trigger"],
                action=instinct["action"],
                domain=instinct["domain"],
                source=instinct["source"],
                confidence=instinct["confidence"],
                thread_id=thread_id,
            )

            # Get the created instinct ID
            created_instincts = storage.list_instincts(thread_id=thread_id, apply_decay=False)
            if created_instincts:
                last_created = created_instincts[-1]
                # Update metadata and timestamps
                conn = storage.get_connection(thread_id)
                try:
                    conn.execute("""
                        UPDATE instincts
                        SET occurrence_count = ?,
                            success_rate = ?,
                            last_triggered = ?,
                            created_at = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        instinct.get("occurrence_count", 0),
                        instinct.get("success_rate", 1.0),
                        instinct.get("last_triggered"),
                        instinct["created_at"],
                        instinct["updated_at"],
                        last_created["id"]
                    ))
                    conn.commit()
                finally:
                    conn.close()

            migrated_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to migrate instinct {instinct.get('id')}: {e}")

    # Verify migration if requested
    verification_passed = True
    if verify and migrated_count > 0:
        verification_passed = _verify_migration(
            instincts, storage, thread_id
        )

    return {
        "status": "success" if verification_passed else "verification_failed",
        "thread_id": thread_id,
        "migrated_count": migrated_count,
        "failed_count": failed_count,
        "jsonl_backed_up": backup,
        "verification_passed": verification_passed,
    }


def _load_instincts_from_json(
    jsonl_path: Path,
    snapshot_path: Path,
) -> list[dict[str, Any]]:
    """Load instincts from JSONL file."""
    instincts = {}

    # Try loading snapshot first (faster)
    if snapshot_path.exists():
        try:
            with open(snapshot_path, "r") as f:
                snapshot = json.load(f)

            # Convert snapshot to list
            for instinct_id, instinct in snapshot.items():
                instincts[instinct_id] = instinct
        except (json.JSONDecodeError, IOError):
            pass

    # Rebuild from JSONL if snapshot failed or to get latest state
    if jsonl_path.exists():
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)

                    if event["event"] == "create":
                        instincts[event["id"]] = {
                            "id": event["id"],
                            "trigger": event["trigger"],
                            "action": event["action"],
                            "domain": event["domain"],
                            "source": event["source"],
                            "confidence": event["confidence"],
                            "occurrence_count": 0,
                            "success_rate": 1.0,
                            "last_triggered": None,
                            "status": "enabled",
                            "created_at": event["ts"],
                            "updated_at": event["ts"],
                        }

                    elif event["event"] in ("confirm", "contradict"):
                        if event["id"] in instincts:
                            instincts[event["id"]]["confidence"] = event.get("new_confidence", 0.5)
                            instincts[event["id"]]["updated_at"] = event["ts"]

                            if instincts[event["id"]]["confidence"] < 0.2:
                                instincts[event["id"]]["status"] = "disabled"

                    elif event["event"] == "reinforce":
                        if event["id"] in instincts:
                            instincts[event["id"]]["occurrence_count"] = event.get("occurrence_count", 0)
                            instincts[event["id"]]["confidence"] = event.get("confidence", instincts[event["id"]]["confidence"])
                            instincts[event["id"]]["updated_at"] = event["ts"]

                    elif event["event"] == "delete":
                        if event["id"] in instincts:
                            del instincts[event["id"]]

                except json.JSONDecodeError:
                    continue

    return list(instincts.values())


def _verify_migration(
    original_instincts: list[dict[str, Any]],
    storage: InstinctStorageSQLite,
    thread_id: str,
) -> bool:
    """Verify that migration was successful."""
    try:
        migrated = storage.list_instincts(thread_id=thread_id, apply_decay=False)

        # Check count
        if len(migrated) != len(original_instincts):
            return False

        # Check each instinct
        for orig in original_instincts:
            found = False
            for mig in migrated:
                if (
                    mig["trigger"] == orig["trigger"]
                    and mig["action"] == orig["action"]
                    and mig["domain"] == orig["domain"]
                ):
                    found = True
                    # Check confidence is close (account for float precision)
                    if abs(mig["confidence"] - orig["confidence"]) > 0.01:
                        return False
                    break

            if not found:
                return False

        return True
    except Exception:
        return False


def migrate_all_threads(
    backup: bool = True,
    verify: bool = True,
) -> dict[str, Any]:
    """
    Migrate all threads from JSON to SQLite.

    Args:
        backup: Whether to backup JSON files
        verify: Whether to verify each migration

    Returns:
        Aggregate migration statistics
    """
    users_root = settings.USERS_ROOT

    if not users_root.exists():
        return {
            "status": "no_data",
            "message": "No users directory found",
        }

    # Find all threads with instincts
    total_migrated = 0
    total_failed = 0
    thread_results = []

    for thread_dir in users_root.iterdir():
        if not thread_dir.is_dir():
            continue

        instincts_dir = thread_dir / "instincts"
        if not instincts_dir.exists():
            continue

        jsonl_path = instincts_dir / "instincts.jsonl"
        if not jsonl_path.exists():
            continue

        thread_id = thread_dir.name

        try:
            result = migrate_thread_to_sqlite(
                thread_id=thread_id,
                backup=backup,
                verify=verify,
            )

            thread_results.append(result)

            if result["status"] == "success":
                total_migrated += result["migrated_count"]
            else:
                total_failed += 1

        except Exception as e:
            total_failed += 1
            thread_results.append({
                "status": "error",
                "thread_id": thread_id,
                "error": str(e),
            })

    return {
        "status": "success" if total_failed == 0 else "partial_failure",
        "total_threads": len(thread_results),
        "successful_threads": len([r for r in thread_results if r["status"] == "success"]),
        "failed_threads": total_failed,
        "total_instincts_migrated": total_migrated,
        "thread_results": thread_results,
    }


def check_migration_status(thread_id: str) -> dict[str, Any]:
    """Check migration status for a specific thread."""
    instincts_dir = settings.get_thread_instincts_dir(thread_id)
    jsonl_path = instincts_dir / "instincts.jsonl"
    db_path = instincts_dir / "instincts.db"

    status = {
        "thread_id": thread_id,
        "has_json": jsonl_path.exists(),
        "has_sqlite": db_path.exists(),
        "migration_complete": db_path.exists(),
    }

    if status["has_sqlite"]:
        # Check SQLite data
        storage = InstinctStorageSQLite()
        instincts = storage.list_instincts(thread_id=thread_id, apply_decay=False)
        status["sqlite_count"] = len(instincts)

    return status
