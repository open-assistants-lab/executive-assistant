"""Thread-scoped system metadata registry.

Stores lightweight inventory info in data/users/{thread_id}/meta.json.
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
    Get the path to meta.json for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        Path to meta.json file in thread-based directory.
    """
    thread_root = settings.get_thread_root(thread_id)
    thread_root.mkdir(parents=True, exist_ok=True)
    return thread_root / "meta.json"


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
        "vdb": {"collections": [], "last_updated": None},
        "tdb": {"path": None, "tables": [], "files": [], "last_updated": None},
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
    if isinstance(vs, dict):
        data.setdefault("vdb", {"collections": [], "last_updated": None})
        if "collections" in vs:
            data["vdb"]["collections"] = vs.get("collections") or []
        elif "tables" in vs:
            data["vdb"]["collections"] = vs.get("tables") or []
        if "last_updated" in vs:
            data["vdb"]["last_updated"] = vs.get("last_updated")
        data.pop("vs", None)
        migrated = True
    data.setdefault("vdb", {"collections": [], "last_updated": None})
    db = data.get("db")
    if isinstance(db, dict):
        data.setdefault("tdb", {"path": None, "tables": [], "files": [], "last_updated": None})
        if "path" in db:
            data["tdb"]["path"] = db.get("path")
        if "tables" in db:
            data["tdb"]["tables"] = db.get("tables") or []
        if "files" in db:
            data["tdb"]["files"] = db.get("files") or []
        if "last_updated" in db:
            data["tdb"]["last_updated"] = db.get("last_updated")
        data.pop("db", None)
        migrated = True
    data.setdefault("tdb", {"path": None, "tables": [], "files": [], "last_updated": None})
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

    vdb = meta.get("vdb", {})
    vdb_collections = [t for t in vdb.get("collections", []) if isinstance(t, str)]
    lines.append(f"VDB collections: {len(vdb_collections)}")
    if vdb_collections:
        lines.append(", ".join(fmt_code(t) for t in vdb_collections[:max_items]))

    db = meta.get("tdb", {})
    db_path = db.get("path")
    db_tables = [t for t in db.get("tables", []) if isinstance(t, str)]
    db_files = [t for t in db.get("files", []) if isinstance(t, str)]
    if db_path:
        lines.append(f"TDB path: {fmt_code(str(db_path))}")
    if db_files:
        lines.append(f"TDB files: {len(db_files)}")
        lines.append(", ".join(fmt_code(t) for t in db_files[:max_items]))
    lines.append(f"TDB tables: {len(db_tables)}")
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
    from executive_assistant.storage.thread_storage import get_thread_id
    from executive_assistant.storage.user_registry import (
        register_file_path_best_effort,
        register_tdb_path_best_effort,
        register_vdb_path_best_effort,
        register_mem_path_best_effort,
        register_adb_path_best_effort,
    )

    meta = _default_meta(thread_id)
    now = _now_iso()
    meta["updated_at"] = now

    thread_id = get_thread_id()
    if not thread_id:
        thread_id = "unknown"

    storage_id = thread_id

    # Files inventory - thread-only storage
    files_root = settings.get_thread_files_path(storage_id)

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

    # VDB tables (LanceDB)
    vdb_collections: list[str] = []
    try:
        from executive_assistant.storage.lancedb_storage import list_lancedb_collections

        vdb_collections = list_lancedb_collections(storage_id=storage_id)
    except Exception:
        vdb_collections = []

    meta["vdb"] = {
        "collections": sorted(vdb_collections)[:MAX_TRACKED_TABLES],
        "last_updated": now,
    }

    # TDB tables - SQLite
    db_path = settings.get_thread_tdb_path(storage_id, "default")
    db_root = settings.get_thread_root(storage_id)

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
                p.name
                for p in db_path.parent.iterdir()
                if p.is_file() and p.suffix == ".sqlite"
            )[:MAX_TRACKED_TABLES]
        except Exception:
            db_files = []

    meta["tdb"] = {
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
        reminders = await storage.list_by_thread(thread_id, None)
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
        paths = {
            _normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)
        }
        paths.add(_normalize_rel_path(relative_path))
        files["paths"] = sorted(paths)[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
        register_file_path_best_effort(thread_id, "unknown", relative_path)
    except Exception:
        return


def record_file_removed(thread_id: str | None, relative_path: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        files = meta["files"]
        target = _normalize_rel_path(relative_path)
        paths = {
            _normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)
        }
        if target in paths:
            paths.remove(target)
        files["paths"] = sorted(paths)[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
        vdb_dir = settings.get_thread_vdb_path(thread_id)
        register_vdb_path_best_effort(thread_id, "unknown", str(vdb_dir))
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
            _normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)
        ]
        kept = [
            p
            for p in paths
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
        paths = {
            _normalize_rel_path(p) for p in files.get("paths", []) if isinstance(p, str)
        }
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


def record_folder_renamed(
    thread_id: str | None, old_prefix: str, new_prefix: str
) -> None:
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
                normalized = (
                    new_prefix_with_sep + normalized[len(old_prefix_with_sep) :]
                )
            updated.append(normalized)
        files["paths"] = sorted(set(updated))[:MAX_TRACKED_FILES]
        files["count"] = len(files["paths"])
        files["last_updated"] = _now_iso()
        meta["updated_at"] = files["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_vdb_table_added(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        vdb = meta["vdb"]
        collections = {t for t in vdb.get("collections", []) if isinstance(t, str)}
        collections.add(table_name)
        vdb["collections"] = sorted(collections)[:MAX_TRACKED_TABLES]
        vdb["last_updated"] = _now_iso()
        meta["updated_at"] = vdb["last_updated"]
        save_meta(thread_id, meta)
        vdb_dir = settings.get_thread_vdb_path(thread_id)
        register_vdb_path_best_effort(thread_id, "unknown", str(vdb_dir))
    except Exception:
        return


def record_vdb_table_removed(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        vdb = meta["vdb"]
        collections = {t for t in vdb.get("collections", []) if isinstance(t, str)}
        if table_name in collections:
            collections.remove(table_name)
        vdb["collections"] = sorted(collections)[:MAX_TRACKED_TABLES]
        vdb["last_updated"] = _now_iso()
        meta["updated_at"] = vdb["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_tdb_table_added(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        db = meta["tdb"]
        tables = {t for t in db.get("tables", []) if isinstance(t, str)}
        tables.add(table_name)
        db["tables"] = sorted(tables)[:MAX_TRACKED_TABLES]
        db["last_updated"] = _now_iso()
        meta["updated_at"] = db["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_tdb_table_removed(thread_id: str | None, table_name: str) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        db = meta["tdb"]
        tables = {t for t in db.get("tables", []) if isinstance(t, str)}
        if table_name in tables:
            tables.remove(table_name)
        db["tables"] = sorted(tables)[:MAX_TRACKED_TABLES]
        db["last_updated"] = _now_iso()
        meta["updated_at"] = db["last_updated"]
        save_meta(thread_id, meta)
    except Exception:
        return


def record_tdb_path(thread_id: str | None, db_path: Path) -> None:
    if not thread_id:
        return
    try:
        meta = load_meta(thread_id)
        db = meta["tdb"]
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
