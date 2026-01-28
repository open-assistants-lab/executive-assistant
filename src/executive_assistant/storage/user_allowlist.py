"""User allowlist for channel-based access control."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from executive_assistant.config.settings import settings


@dataclass(frozen=True)
class Allowlist:
    users: set[str]
    updated_at: str | None = None


def _allowlist_path() -> Path:
    path = settings.ADMINS_ROOT / "user_allowlist.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_entry(entry: str) -> str:
    entry = entry.strip()
    if ":" not in entry:
        raise ValueError("Entry must be in the form <channel>:<id>")
    channel, ident = entry.split(":", 1)
    channel = channel.strip().lower()
    ident = ident.strip()
    if not channel or not ident:
        raise ValueError("Entry must include both channel and id")
    return f"{channel}:{ident}"


def normalize_entry(entry: str) -> str:
    return _normalize_entry(entry)


def is_admin(thread_id: str | None) -> bool:
    if thread_id and thread_id in settings.ADMIN_THREAD_IDS:
        return True
    return False


def is_admin_entry(entry: str) -> bool:
    normalized = _normalize_entry(entry)
    if normalized in settings.ADMIN_THREAD_IDS:
        return True
    return False


def is_authorized(thread_id: str | None) -> bool:
    if thread_id is None:
        return False
    if is_admin(thread_id):
        return True
    return is_allowed(thread_id)


def load_allowlist() -> Allowlist:
    path = _allowlist_path()
    if not path.exists():
        return Allowlist(users=set(), updated_at=None)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        users = {str(u) for u in data.get("users", []) if str(u).strip()}
        return Allowlist(users=users, updated_at=data.get("updated_at"))
    except Exception:
        return Allowlist(users=set(), updated_at=None)


def save_allowlist(users: set[str]) -> None:
    path = _allowlist_path()
    payload = {
        "users": sorted(users),
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")




def allowlist_writable() -> bool:
    path = _allowlist_path()
    parent = path.parent
    if path.exists():
        return path.is_file() and os.access(path, os.W_OK)
    return parent.is_dir() and os.access(parent, os.W_OK)


def is_allowed(entry: str) -> bool:
    allowlist = load_allowlist()
    normalized = _normalize_entry(entry)
    return normalized in allowlist.users


def list_users() -> list[str]:
    allowlist = load_allowlist()
    return sorted(allowlist.users)


def add_user(entry: str) -> bool:
    allowlist = load_allowlist()
    normalized = _normalize_entry(entry)
    if normalized in allowlist.users:
        return False
    users = set(allowlist.users)
    users.add(normalized)
    save_allowlist(users)
    return True


def remove_user(entry: str) -> bool:
    allowlist = load_allowlist()
    normalized = _normalize_entry(entry)
    if normalized not in allowlist.users:
        return False
    users = set(allowlist.users)
    users.remove(normalized)
    save_allowlist(users)
    return True
