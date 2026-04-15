"""User storage utilities."""

from src.storage.paths import get_paths


def get_all_user_ids() -> list[str]:
    """Get all user IDs from data/private directory."""
    users_path = get_paths().private
    if not users_path.exists():
        return []

    user_ids = []
    for item in users_path.parent.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            user_ids.append(item.name)

    return user_ids
