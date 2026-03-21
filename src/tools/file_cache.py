"""File cache tracking for sync status."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class FileCache:
    """Track which files are cached/downloaded."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.cache_file = Path(f"data/users/{user_id}/workspace/.file_cache.json")
        self._cache: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_file.exists():
            try:
                self._cache = json.loads(self.cache_file.read_text())
            except Exception:
                self._cache = {}

    def _save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self._cache, indent=2))

    def get_status(self, path: str) -> str:
        """Get sync status: 'cloud_only', 'downloaded', 'pinned'"""
        return self._cache.get(path, {}).get("status", "cloud_only")

    def mark_downloaded(self, path: str) -> None:
        self._cache[path] = {
            "status": "downloaded",
            "downloaded_at": datetime.now(UTC).isoformat(),
        }
        self._save()

    def mark_pinned(self, path: str) -> None:
        self._cache[path] = {
            "status": "pinned",
            "pinned_at": datetime.now(UTC).isoformat(),
        }
        self._save()

    def mark_cloud_only(self, path: str) -> None:
        if path in self._cache:
            del self._cache[path]
            self._save()

    def get_all(self, workspace_path: str = "data/users") -> dict[str, dict[str, Any]]:
        """Get all sync status with has_update flag."""
        result = {}
        user_workspace = Path(workspace_path).joinpath(self.user_id).joinpath("workspace")

        for path, data in self._cache.items():
            file_path = user_workspace / path
            server_modified = str(file_path.stat().st_mtime) if file_path.exists() else ""
            current_version = data.get("server_modified", "")

            result[path] = {
                **data,
                "has_update": server_modified != current_version if server_modified else False,
            }

        return result

    def get_last_synced(self, path: str) -> str | None:
        """Get last sync timestamp for a file."""
        return self._cache.get(path, {}).get("synced_at")

    def update_sync(self, path: str, server_modified: str) -> bool:
        """Update sync timestamp. Returns True if file changed (needs re-download)."""
        existing = self._cache.get(path, {})
        last_synced = existing.get("synced_at")

        # If never synced or server version changed, mark for re-download
        if last_synced is None or existing.get("server_modified") != server_modified:
            self._cache[path] = {
                "status": "downloaded",
                "synced_at": datetime.now(UTC).isoformat(),
                "server_modified": server_modified,
            }
            self._save()
            return True
        return False

    def get_downloaded_files(self) -> list[str]:
        return [
            path
            for path, data in self._cache.items()
            if data.get("status") in ("downloaded", "pinned")
        ]


def get_file_cache(user_id: str) -> FileCache:
    return FileCache(user_id)
