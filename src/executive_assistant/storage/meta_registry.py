"""User-scoped system metadata registry.

Stores lightweight inventory info in data/users/{user_id}/meta.json.
User_id is automatically derived from thread_id (anon_* format or user_* after merge).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from executive_assistant.config import settings

MAX_TRACKED_FILES = 200
MAX_TRACKED_TABLES = 100
MAX_TRACKED_REMINDERS = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _meta_path(thread_id: str) -> Path:
    """
    Get the path to meta.json for a user (converted from thread_id).

    Args:
        thread_id: Thread identifier (will be converted to user_id for path)

    Returns:
        Path to meta.json file in user-based directory.
    """
    # Convert thread_id to user_id for user-based storage
    # If the id is already a user id (anon_/user_), use it directly.
    if ":" in thread_id:
        from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id
        user_id = sanitize_thread_id_to_user_id(thread_id)
    else:
        user_id = thread_id

    # Use user-based path
    user_root = settings.get_user_root(user_id)
    user_root.mkdir(parents=True, exist_ok=True)
    return user_root / "meta.json"


def _normalize_rel_path(path: str) -> str:
    normalized = path.strip().lstrip("./").replace("\\", "/")
    if normalized.endswith("/") and normalized != "/":
        normalized = normalized[:-1]
    return normalized


def _default_meta(thread_id: str) -> dict[str, Any]:
    now = _now_iso()
    return {
        "thread_id": thread_id,
        "updated_at": now,
        "files": {"paths": [], "count": 0, "last_updated": None},
        "vs": {"collections": [], "last_updated": None},
        "db": {"path": None, "tables": [], "files": [], "last_updated": None},
        "reminders": {"count": 0, "items": [], "last_updated": None},
    }


def load_meta(thread_id: str) -> dict[str, Any]:
    path = _meta_path(thread_id)
    if not path.exists():
        return _default_meta(thread_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_meta(thread_id)
    if not isinstance(data, dict):
        return _default_meta(thread_id)
    migrated = False
    data.setdefault("thread_id", thread_id)
    data.setdefault("files", {"paths": [], "count": 0, "last_updated": None})
    vs = data.get("vs")
    if isinstance(vs, dict) and "collections" not in vs and "tables" in vs:
        vs["collections"] = vs.pop("tables") or []
        migrated = True
    data.setdefault("vs", {"collections": [], "last_updated": None})
    db = data.get("db")
    if isinstance(db, dict) and "files" not in db:
        db["files"] = []
        migrated = True
    data.setdefault("db", {"path": None, "tables": [], "files": [], "last_updated": None})
    reminders = data.get("reminders")
    if isinstance(reminders, dict) and "items" not in reminders:
        reminders["items"] = []
        migrated = True
    data.setdefault("reminders", {"count": 0, "items": [], "last_updated": None})
    if migrated:
        save_meta(thread_id, data)
    return data


def save_meta(thread_id: str, data: dict[str, Any]) -> None:
    path = _meta_path(thread_id)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def format_meta(
    meta: dict[str, Any],
    markdown: bool = False,
    max_items: int = 20,
) -> str:
    """Format meta registry data for display."""
    def fmt_code(value: str) -> str:
        return f"`{value}`" if markdown else value

    thread_id = str(meta.get("thread_id", ""))
    lines = []
    if markdown:
        lines.append("🧭 *System Inventory*")
    else:
        lines.append("System Inventory")

    if thread_id:
        lines.append(f"Thread: {fmt_code(thread_id)}")

    files = meta.get("files", {})
    file_count = int(files.get("count") or 0)
    file_paths = [p for p in files.get("paths", []) if isinstance(p, str)]
    lines.append(f"Files: {file_count}")
    if file_paths:
        shown = file_paths[:max_items]
        for path in shown:
            lines.append(f"- {fmt_code(path)}")
        if file_count > len(shown):
            lines.append(f"... {file_count - len(shown)} more")

    vs = meta.get("vs", {})
    vs_collections = [t for t in vs.get("collections", []) if isinstance(t, str)]
    lines.append(f"VS collections: {len(vs_collections)}")
    if vs_collections:
        lines.append(", ".join(fmt_code(t) for t in vs_collections[:max_items]))

    db = meta.get("db", {})
    db_path = db.get("path")
    db_tables = [t for t in db.get("tables", []) if isinstance(t, str)]
    db_files = [t for t in db.get("files", []) if isinstance(t, str)]
    if db_path:
        lines.append(f"DB path: {fmt_code(str(db_path))}")
    if db_files:
        lines.append(f"DB files: {len(db_files)}")
        lines.append(", ".join(fmt_code(t) for t in db_files[:max_items]))
    lines.append(f"DB tables: {len(db_tables)}")
    if db_tables:
        lines.append(", ".join(fmt_code(t) for t in db_tables[:max_items]))

    reminders = meta.get("reminders", {})
    reminder_count = int(reminders.get("count") or 0)
    lines.append(f"Reminders: {reminder_count}")
    reminder_items = reminders.get("items", [])
    if reminder_items:
        shown = reminder_items[:max_items]
        for item in shown:
            if not isinstance(item, dict):
                continue
            reminder_id = item.get("id")
            message = item.get("message")
            if reminder_id is not None and message:
                lines.append(f"- {fmt_code(str(reminder_id))}: {message}")

    return "\n".join(lines)


async def refresh_meta(thread_id: str) -> dict[str, Any]:
    """Rebuild meta.json by scanning files/KB/DB/reminders."""
    from executive_assistant.storage.group_storage import get_workspace_id

    meta = _default_meta(thread_id)
    now = _now_iso()
    meta["updated_at"] = now

    # Priority: user_id (individual) > group_id (team) > thread_id (fallback)
    from executive_assistant.storage.group_storage import get_user_id
    user_id = get_user_id()
    group_id = get_workspace_id()

    if user_id:
        storage_id = user_id
        is_group = False
    elif group_id:
        storage_id = group_id
        is_group = True
    else:
        storage_id = thread_id
        is_group = False

    # Files inventory - use group/user path based on context
    if is_group:
        files_root = settings.get_group_files_path(storage_id)
    else:
        files_root = settings.get_user_files_path(storage_id)

    file_paths: list[str] = []
    total_files = 0
    if files_root.exists():
        for root, _, files in os.walk(files_root):
            for filename in files:
                total_files += 1
                full_path = Path(root) / filename
                try:
                    rel_path = full_path.relative_to(files_root).as_posix()
                except ValueError:
                    rel_path = full_path.as_posix()
                file_paths.append(rel_path)

    file_paths = sorted(file_paths)
    meta["files"] = {
        "paths": file_paths[:MAX_TRACKED_FILES],
        "count": total_files,
        "last_updated": now,
    }

    # VS tables (LanceDB)
    vs_collections: list[str] = []
    try:
        from executive_assistant.storage.lancedb_storage import list_lancedb_collections

        vs_collections = list_lancedb_collections(storage_id=storage_id)
    except Exception:
        vs_collections = []

    meta["vs"] = {
        "collections": sorted(vs_collections)[:MAX_TRACKED_TABLES],
        "last_updated": now,
    }

    # DB tables - SQLite
    if is_group:
        db_path = settings.get_group_db_path(storage_id, "default")
        db_root = settings.get_group_root(storage_id)
    else:
        db_path = settings.get_user_db_path(storage_id, "default")
        db_root = settings.get_user_root(storage_id)

    db_tables: list[str] = []
    db_path_value: str | None = None
    db_files: list[str] = []
    if db_path.exists():
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            try:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                db_tables = [row[0] for row in rows]
            finally:
                conn.close()

            try:
                rel_path = db_path.relative_to(db_root)
                db_path_value = rel_path.as_posix()
            except ValueError:
                db_path_value = str(db_path)
        except Exception:
            db_tables = []
    if db_path.parent.exists():
        try:
            db_files = sorted(
                p.name for p in db_path.parent.iterdir()
                if p.is_file() and p.suffix == ".sqlite"
            )[:MAX_TRACKED_TABLES]
        except Exception:
            db_files = []

    meta["db"] = {
        "path": db_path_value,
        "tables": sorted(db_tables)[:MAX_TRACKED_TABLES],
        "files": db_files,
        "last_updated": now,
    }

    # Reminders
    reminder_count = 0
    reminder_items: list[dict[str, Any]] = []
    try:
        from executive_assistant.storage.reminder import get_reminder_storage

        storage = await get_reminder_storage()
        reminders = await storage.list_by_user(thread_id, None)
        reminder_count = len(reminders)
        reminder_items = [
            {
                "id": reminder.id,
                "message": reminder.message,
                "due_time": reminder.due_time.isoformat(),
                "status": reminder.status,
                "recurrence": reminder.recurrence,
            }
            for reminder in reminders[:MAX_TRACKED_REMINDERS]
        ]
    except Exception:
        reminder_count = 0
        reminder_items = []

    meta["reminders"] = {
        "count": reminder_count,
        "items": reminder_items,
        "last_updated": now,
    }

    save_meta(thread_id, meta)
    return meta


def record_file_written(thread_id: str | None, relative_path: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        files = meta["files"]
        paths = {_normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)}
        paths.add(_normalize_rel_path(relative_path))
        files["paths"] = sorted(paths)[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_file_removed(thread_id: str | None, relative_path: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        files = meta["files"]
        target = _normalize_rel_path(relative_path)
        paths = {_normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)}
        if target in paths:
            paths.remove(target)
        files["paths"] = sorted(paths)[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_files_removed_by_prefix(thread_id: str | None, prefix: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        files = meta["files"]
        normalized_prefix = _normalize_rel_path(prefix)
        prefix_with_sep = normalized_prefix + "/"
        paths = [
            _normalize_rel_path(p)
            for p in files.get("paths", [])
            if isinstance(p, str)
        ]
        kept = [
            p for p in paths
            if p != normalized_prefix and not p.startswith(prefix_with_sep)
        ]
        files["paths"] = sorted(set(kept))[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_file_moved(thread_id: str | None, source: str, destination: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        files = meta["files"]
        paths = {_normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)}
        source_norm = _normalize_rel_path(source)
        dest_norm = _normalize_rel_path(destination)
        if source_norm in paths:
            paths.remove(source_norm)
        paths.add(dest_norm)
        files["paths"] = sorted(paths)[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_folder_renamed(thread_id: str | None, old_prefix: str, new_prefix: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        files = meta["files"]
        old_norm = _normalize_rel_path(old_prefix)
        new_norm = _normalize_rel_path(new_prefix)
        old_prefix_with_sep = old_norm + "/"
        new_prefix_with_sep = new_norm + "/"
        updated: list[str] = []
        for p in files.get("paths", []):
            if not isinstance(p, str):
                continue
            normalized = _normalize_rel_path(p)
            if normalized == old_norm:
                normalized = new_norm
            elif normalized.startswith(old_prefix_with_sep):
                normalized = new_prefix_with_sep + normalized[len(old_prefix_with_sep):]
            updated.append(normalized)
        files["paths"] = sorted(set(updated))[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_vs_table_added(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        vs = meta["vs"]
        collections = {t for t in vs.get("collections", []) if isinstance(t, str)}
        collections.add(table_name)
        vs["collections"] = sorted(collections)[:MAX_TRACKED_TABLES]
        vs["last_updated"] = _now_iso()
        meta["updated_at"] = vs["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_vs_table_removed(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        vs = meta["vs"]
        collections = {t for t in vs.get("collections", []) if isinstance(t, str)}
        if table_name in collections:
            collections.remove(table_name)
        vs["collections"] = sorted(collections)[:MAX_TRACKED_TABLES]
        vs["last_updated"] = _now_iso()
        meta["updated_at"] = vs["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_db_table_added(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        db = meta["db"]
        tables = {t for t in db.get("tables", []) if isinstance(t, str)}
        tables.add(table_name)
        db["tables"] = sorted(tables)[:MAX_TRACKED_TABLES]
        db["last_updated"] = _now_iso()
        meta["updated_at"] = db["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_db_table_removed(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        db = meta["db"]
        tables = {t for t in db.get("tables", []) if isinstance(t, str)}
        if table_name in tables:
            tables.remove(table_name)
        db["tables"] = sorted(tables)[:MAX_TRACKED_TABLES]
        db["last_updated"] = _now_iso()
        meta["updated_at"] = db["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_db_path(thread_id: str | None, db_path: Path) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        db = meta["db"]
        thread_root = settings.get_thread_root(thread_id)
        try:
            rel_path = db_path.relative_to(thread_root)
            db["path"] = rel_path.as_posix()
        except ValueError:
            db["path"] = str(db_path)
        db["last_updated"] = _now_iso()
        meta["updated_at"] = db["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_reminder_count(thread_id: str | None, count: int) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        reminders = meta["reminders"]
        reminders["count"] = int(count)
        reminders["last_updated"] = _now_iso()
        meta["updated_at"] = reminders["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return
