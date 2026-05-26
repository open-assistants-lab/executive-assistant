#!/usr/bin/env python3
"""One-shot migration: move data/users/{id}/ → ~/Executive Assistant/.

Usage:
    python scripts/migrate-paths.py [--dry-run]

Guardrails:
    - Dry-run mode: prints what would move without touching disk
    - Resume marker: ~/.ea_migrated prevents re-run
    - Case-insensitive FS fix: rename lowercase → uppercase via temp dir
"""

import argparse
import json
import os
import shutil
import sys
import warnings
from pathlib import Path

EA_ROOT = Path.home() / "Executive Assistant"
DATA_PATH = Path("data")
MIGRATED_MARKER = Path.home() / ".ea_migrated"

FILE_MAP = [
    # (source relative to data/users/{user_id}/, destination relative to EA_ROOT)
    ("config/prompt.txt", "AGENTS.md"),
    ("skills", "Skills"),
    ("subagents", "Subagents"),
    ("conversation", "Conversation"),
    ("memory", "Memory/global"),
    ("email", "Email"),
    ("gmail_cache", "Email/gmail_cache"),
    ("contacts", "Contacts"),
    ("todos", "Todos"),
    ("companion", "Companion"),
    ("apps", "Apps"),
    (".mcp.json", ".mcp.json"),
]

RESEARCH_SOURCE = DATA_PATH / "private" / "research"
RESEARCH_DEST = EA_ROOT / "Research"

WS_SUBDIR_MAP = [
    ("skills", "Skills"),
    ("subagents", "Subagents"),
    ("files", "Files"),
    ("memory", "Memory"),
]


def dry_run(msg):
    print(f"[DRY-RUN] {msg}")


def do_move(src, dst, is_dry_run):
    if is_dry_run:
        dry_run(f"mv {src} → {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    print(f"  ✓ {src} → {dst}")


def migrate_user(user_id, is_dry_run):
    user_dir = DATA_PATH / "users" / user_id
    if not user_dir.exists():
        return

    for rel_src, rel_dst in FILE_MAP:
        src = user_dir / rel_src
        if not src.exists():
            continue
        dst = EA_ROOT / rel_dst
        if dst.exists() and is_dry_run:
            dry_run(f"SKIP {rel_src} → {rel_dst} (destination exists)")
            continue
        if not is_dry_run and dst.exists():
            print(f"  ⚠ SKIP {rel_src} → {rel_dst} (destination exists)")
            continue
        do_move(src, dst, is_dry_run)


def migrate_research(is_dry_run):
    if not RESEARCH_SOURCE.exists():
        return
    if RESEARCH_DEST.exists():
        print(f"  ⚠ SKIP research → Research (destination exists)")
        return
    do_move(RESEARCH_SOURCE, RESEARCH_DEST, is_dry_run)


def migrate_workspace_subdirs(is_dry_run):
    ws_base = EA_ROOT / "Workspaces"
    if not ws_base.exists():
        return
    for ws_dir in ws_base.iterdir():
        if not ws_dir.is_dir():
            continue
        for old_name, new_name in WS_SUBDIR_MAP:
            old_path = ws_dir / old_name
            if not old_path.exists():
                continue
            new_path = ws_dir / new_name
            if new_path.exists():
                continue
            if is_dry_run:
                dry_run(f"mv {old_path} → {new_path}")
                continue
            tmp = ws_dir / f"{old_name}.ea-migrate-tmp"
            shutil.move(str(old_path), str(tmp))
            shutil.move(str(tmp), str(new_path))
            print(f"  ✓ {old_path.relative_to(EA_ROOT)} → {new_path.relative_to(EA_ROOT)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if MIGRATED_MARKER.exists():
        print("Migration already completed. Remove ~/.ea_migrated to re-run.")
        return

    if not args.dry_run:
        warnings.warn(
            "STOP THE BACKEND FIRST! Running migration while the app is live "
            "can corrupt SQLite databases (email, contacts, todos, conversation) "
            "that are being written to under data/users/{id}/. "
            "Use --dry-run to preview, then stop the app and re-run without --dry-run.",
            RuntimeWarning,
            stacklevel=2,
        )
        print("WARNING: Stop the backend before migration! (use --dry-run to preview)")

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Migrating data/ → ~/Executive Assistant/")
    print()

    users_root = DATA_PATH / "users"
    if users_root.exists():
        for user_dir in sorted(users_root.iterdir()):
            if user_dir.is_dir():
                print(f"\nUser: {user_dir.name}")
                migrate_user(user_dir.name, args.dry_run)

    print("\nResearch:")
    migrate_research(args.dry_run)

    print("\nWorkspace subdirs (lowercase → uppercase):")
    migrate_workspace_subdirs(args.dry_run)

    if not args.dry_run:
        MIGRATED_MARKER.write_text("", encoding="utf-8")
        print(f"\n✅ Migration complete. Marker: {MIGRATED_MARKER}")
    else:
        print(f"\n[DRY-RUN] Complete. No files moved.")


if __name__ == "__main__":
    main()
