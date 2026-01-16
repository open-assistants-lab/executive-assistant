#!/usr/bin/env python3
"""Data migration script for moving to consolidated per-thread storage.

Migrates from:
    data/files/{thread_id}/
    data/db/{thread_id}.db
    data/kb/{thread_id}.db

To:
    data/users/{thread_id}/
        files/
        db/main.db
        kb/main.db
"""

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from cassey.config import settings
from cassey.storage.user_registry import sanitize_thread_id


# Migration state file
MIGRATION_STATE_FILE = Path("./data/.migration/state.json")


def sanitize_thread_id_safe(thread_id: str) -> str:
    """Sanitize thread_id for use as directory name."""
    replacements = {":": "_", "/": "_", "@": "_", "\\": "_"}
    for old, new in replacements.items():
        thread_id = thread_id.replace(old, new)
    return thread_id


def load_migration_state() -> dict[str, Any]:
    """Load migration state from file."""
    if MIGRATION_STATE_FILE.exists():
        return json.loads(MIGRATION_STATE_FILE.read_text())
    return {
        "status": "not_started",
        "completed_steps": [],
        "started_at": None,
        "completed_at": None,
        "thread_ids": [],
        "errors": [],
    }


def save_migration_state(state: dict[str, Any]) -> None:
    """Save migration state to file."""
    MIGRATION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MIGRATION_STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def get_source_thread_ids() -> list[str]:
    """
    Get all thread IDs from the old storage structure.

    Scans data/files/, data/db/, and data/kb/ for thread IDs.
    """
    thread_ids = set()

    # From files directory
    files_root = settings.FILES_ROOT
    if files_root.exists():
        for item in files_root.iterdir():
            if item.is_dir():
                thread_ids.add(item.name)

    # From db directory
    db_root = settings.DB_ROOT
    if db_root.exists():
        for item in db_root.iterdir():
            if item.is_file() and item.suffix == ".db":
                thread_ids.add(item.stem)

    # From kb directory
    kb_root = settings.KB_ROOT
    if kb_root.exists():
        for item in kb_root.iterdir():
            if item.is_file() and item.suffix == ".db":
                thread_ids.add(item.stem)

    return sorted(thread_ids)


def validate_pre_migration(thread_ids: list[str]) -> list[str]:
    """
    Validate before migration.

    Returns list of validation errors. Empty list means validation passed.
    """
    errors = []

    # Check for disk space (basic check)
    data_root = Path("./data")
    if data_root.exists():
        # Get total size of old data
        total_size = 0
        for thread_id in thread_ids:
            # Files
            files_path = settings.FILES_ROOT / thread_id
            if files_path.exists():
                for item in files_path.rglob("*"):
                    if item.is_file():
                        total_size += item.stat().st_size

            # DB
            db_path = settings.DB_ROOT / f"{thread_id}.db"
            if db_path.exists():
                total_size += db_path.stat().st_size

            # KB
            kb_path = settings.KB_ROOT / f"{thread_id}.db"
            if kb_path.exists():
                total_size += kb_path.stat().st_size

        # Simple disk space check (2x the size needed)
        # This is a basic check; real implementation would use shutil.disk_usage
        if total_size > 0:
            print(f"Estimated migration size: {total_size / 1024 / 1024:.2f} MB")

    # Check for new layout already existing
    for thread_id in thread_ids:
        new_path = settings.USERS_ROOT / thread_id
        if new_path.exists():
            errors.append(f"New layout already exists for thread_id: {thread_id}")

    # Check if source paths exist
    for thread_id in thread_ids:
        files_path = settings.FILES_ROOT / thread_id
        db_path = settings.DB_ROOT / f"{thread_id}.db"
        kb_path = settings.KB_ROOT / f"{thread_id}.db"

        if not files_path.exists() and not db_path.exists() and not kb_path.exists():
            errors.append(f"No source data found for thread_id: {thread_id}")

    return errors


def migrate_thread(thread_id: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Migrate a single thread to the new structure.

    Args:
        thread_id: Thread identifier (can be raw or sanitized).

    Returns:
        Dict with migration results for this thread.
    """
    # Sanitize thread_id for use in paths
    safe_thread_id = sanitize_thread_id_safe(thread_id)

    result = {
        "thread_id": thread_id,
        "safe_thread_id": safe_thread_id,
        "success": False,
        "files_migrated": 0,
        "db_migrated": False,
        "kb_migrated": False,
        "errors": [],
    }

    try:
        # New paths
        new_root = settings.USERS_ROOT / safe_thread_id
        new_files_path = new_root / "files"
        new_db_path = new_root / "db" / "main.db"
        new_kb_path = new_root / "kb" / "main.db"

        # Old paths (use sanitized thread_id as old layout also used sanitized names)
        old_files_path = settings.FILES_ROOT / safe_thread_id
        old_db_path = settings.DB_ROOT / f"{safe_thread_id}.db"
        old_kb_path = settings.KB_ROOT / f"{safe_thread_id}.db"

        # Migrate files
        if old_files_path.exists():
            if dry_run:
                result["files_migrated"] = sum(
                    1 for _ in old_files_path.rglob("*") if _.is_file()
                )
                print(f"  [DRY RUN] Would migrate {result['files_migrated']} files from {old_files_path}")
            else:
                new_files_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(old_files_path, new_files_path, dirs_exist_ok=True)
                result["files_migrated"] = sum(
                    1 for _ in new_files_path.rglob("*") if _.is_file()
                )
                print(f"  Migrated {result['files_migrated']} files to {new_files_path}")

        # Migrate database
        if old_db_path.exists():
            if dry_run:
                result["db_migrated"] = True
                print(f"  [DRY RUN] Would migrate DB from {old_db_path}")
            else:
                new_db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_db_path, new_db_path)
                result["db_migrated"] = True
                print(f"  Migrated DB to {new_db_path}")

        # Migrate KB
        if old_kb_path.exists():
            if dry_run:
                result["kb_migrated"] = True
                print(f"  [DRY RUN] Would migrate KB from {old_kb_path}")
            else:
                new_kb_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_kb_path, new_kb_path)
                result["kb_migrated"] = True
                print(f"  Migrated KB to {new_kb_path}")

        result["success"] = True

    except Exception as e:
        result["errors"].append(str(e))

    return result


def verify_migration(thread_ids: list[str]) -> dict[str, Any]:
    """
    Verify migration by checking file counts and database integrity.

    Args:
        thread_ids: List of thread identifiers (can be raw or sanitized).

    Returns:
        Dict with verification results.
    """
    results = {
        "total_threads": len(thread_ids),
        "verified_threads": 0,
        "failed_threads": [],
        "errors": [],
    }

    for thread_id in thread_ids:
        safe_thread_id = sanitize_thread_id_safe(thread_id)
        try:
            # Check new paths exist
            new_root = settings.USERS_ROOT / safe_thread_id
            new_files_path = new_root / "files"
            new_db_path = new_root / "db" / "main.db"
            new_kb_path = new_root / "kb" / "main.db"

            old_files_path = settings.FILES_ROOT / safe_thread_id
            old_db_path = settings.DB_ROOT / f"{safe_thread_id}.db"
            old_kb_path = settings.KB_ROOT / f"{safe_thread_id}.db"

            # Verify files count matches
            old_file_count = (
                sum(1 for _ in old_files_path.rglob("*") if _.is_file())
                if old_files_path.exists()
                else 0
            )
            new_file_count = (
                sum(1 for _ in new_files_path.rglob("*") if _.is_file())
                if new_files_path.exists()
                else 0
            )

            if old_file_count != new_file_count:
                results["failed_threads"].append(
                    f"{thread_id}: file count mismatch (old={old_file_count}, new={new_file_count})"
                )
                continue

            # Verify database integrity (SQLite PRAGMA integrity_check)
            if old_db_path.exists() and new_db_path.exists():
                try:
                    conn = sqlite3.connect(str(new_db_path))
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    integrity_result = cursor.fetchone()
                    conn.close()

                    if integrity_result[0] != "ok":
                        results["failed_threads"].append(
                            f"{thread_id}: database integrity check failed"
                        )
                        continue
                except Exception as e:
                    results["failed_threads"].append(
                        f"{thread_id}: database verification error: {e}"
                    )
                    continue

            # Verify KB integrity
            if old_kb_path.exists() and new_kb_path.exists():
                try:
                    conn = sqlite3.connect(str(new_kb_path))
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    integrity_result = cursor.fetchone()
                    conn.close()

                    if integrity_result[0] != "ok":
                        results["failed_threads"].append(
                            f"{thread_id}: KB integrity check failed"
                        )
                        continue
                except Exception as e:
                    results["failed_threads"].append(
                        f"{thread_id}: KB verification error: {e}"
                    )
                    continue

            results["verified_threads"] += 1

        except Exception as e:
            results["errors"].append(f"{thread_id}: {e}")

    return results


def rollback_migration(thread_ids: list[str]) -> dict[str, Any]:
    """
    Rollback migration by removing new layout.

    Note: This only removes the migrated data, does not restore deleted old data.
    Old data should only be deleted after successful verification.

    Args:
        thread_ids: List of thread identifiers (can be raw or sanitized).

    Returns:
        Dict with rollback results.
    """
    results = {
        "total_threads": len(thread_ids),
        "rolled_back_threads": 0,
        "errors": [],
    }

    for thread_id in thread_ids:
        safe_thread_id = sanitize_thread_id_safe(thread_id)
        try:
            new_root = settings.USERS_ROOT / safe_thread_id
            if new_root.exists():
                shutil.rmtree(new_root)
                results["rolled_back_threads"] += 1
                print(f"  Rolled back {thread_id}")
        except Exception as e:
            results["errors"].append(f"{thread_id}: {e}")

    # Also remove state file
    if MIGRATION_STATE_FILE.exists():
        MIGRATION_STATE_FILE.unlink()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate data to consolidated per-thread storage"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing migration",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (remove new layout)",
    )
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help="Delete old data after successful verification (use with caution)",
    )

    args = parser.parse_args()

    # Check migration state
    state = load_migration_state()

    if args.rollback:
        print("Rolling back migration...")
        if state["status"] == "completed":
            thread_ids = state["thread_ids"]
        else:
            thread_ids = get_source_thread_ids()

        results = rollback_migration(thread_ids)
        print(f"Rolled back {results['rolled_back_threads']}/{results['total_threads']} threads")
        if results["errors"]:
            print("Errors:")
            for error in results["errors"]:
                print(f"  {error}")
        return

    if args.verify_only:
        print("Verifying migration...")
        thread_ids = get_source_thread_ids()
        results = verify_migration(thread_ids)
        print(f"Verified: {results['verified_threads']}/{results['total_threads']} threads")
        if results["failed_threads"]:
            print("Failed threads:")
            for failure in results["failed_threads"]:
                print(f"  {failure}")
        if results["errors"]:
            print("Errors:")
            for error in results["errors"]:
                print(f"  {error}")
        return

    # Get thread IDs to migrate
    thread_ids = get_source_thread_ids()

    if not thread_ids:
        print("No thread IDs found to migrate.")
        return

    print(f"Found {len(thread_ids)} thread(s) to migrate:")
    for thread_id in thread_ids:
        print(f"  - {thread_id}")

    # Pre-migration validation
    print("\nValidating pre-migration...")
    validation_errors = validate_pre_migration(thread_ids)
    if validation_errors:
        print("Validation errors:")
        for error in validation_errors:
            print(f"  - {error}")
        return

    print("Validation passed.")

    # Dry run or actual migration
    if args.dry_run:
        print("\n[DRY RUN] Showing migration plan...")
        for thread_id in thread_ids:
            print(f"\nThread: {thread_id}")
            migrate_thread(thread_id, dry_run=True)
        print("\n[DRY RUN] No changes made. Run without --dry-run to perform migration.")
        return

    # Actual migration
    print("\nStarting migration...")
    state["status"] = "in_progress"
    state["started_at"] = datetime.now().isoformat()
    state["thread_ids"] = thread_ids
    save_migration_state(state)

    migration_results = []
    for thread_id in thread_ids:
        print(f"\nMigrating {thread_id}...")
        result = migrate_thread(thread_id, dry_run=False)
        migration_results.append(result)

        if not result["success"]:
            state["errors"].append(f"{thread_id}: {result['errors']}")

    # Verification
    print("\nVerifying migration...")
    verification_results = verify_migration(thread_ids)

    print(f"Verified: {verification_results['verified_threads']}/{verification_results['total_threads']} threads")

    if verification_results["failed_threads"]:
        print("\nVerification failed for:")
        for failure in verification_results["failed_threads"]:
            print(f"  {failure}")
        print("\nPlease review and run rollback if needed:")
        print("  python scripts/migrate_data.py --rollback")
        return

    # Migration successful
    state["status"] = "completed"
    state["completed_at"] = datetime.now().isoformat()
    state["completed_steps"] = ["files", "db", "kb"]
    save_migration_state(state)

    print("\nMigration completed successfully!")
    print(f"State saved to: {MIGRATION_STATE_FILE}")

    # Ask about deleting old data
    if not args.delete_old:
        print("\nOld data is preserved. To delete after verification, run:")
        print("  python scripts/migrate_data.py --delete-old")
        return

    # Delete old data
    print("\nDeleting old data...")
    for thread_id in thread_ids:
        old_files_path = settings.FILES_ROOT / thread_id
        old_db_path = settings.DB_ROOT / f"{thread_id}.db"
        old_kb_path = settings.KB_ROOT / f"{thread_id}.db"

        if old_files_path.exists():
            shutil.rmtree(old_files_path)
            print(f"  Deleted {old_files_path}")

        if old_db_path.exists():
            old_db_path.unlink()
            print(f"  Deleted {old_db_path}")

        if old_kb_path.exists():
            old_kb_path.unlink()
            print(f"  Deleted {old_kb_path}")

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
