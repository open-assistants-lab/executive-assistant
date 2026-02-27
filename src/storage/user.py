"""User storage utilities."""

from pathlib import Path


def get_all_user_ids() -> list[str]:
    """Get all user IDs from data/users directory."""
    users_path = Path("data/users")
    if not users_path.exists():
        return []

    user_ids = []
    for item in users_path.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            user_ids.append(item.name)

    return user_ids
