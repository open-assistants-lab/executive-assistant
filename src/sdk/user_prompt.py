"""Per-user prompt storage — persisted custom instructions across workspaces."""

from pathlib import Path

from src.storage.paths import get_paths


USER_PROMPT_FILENAME = "prompt.txt"


def _user_prompt_path(user_id: str) -> Path:
    paths = get_paths(user_id)
    return paths.user_config_dir() / USER_PROMPT_FILENAME


def load_user_prompt(user_id: str = "default_user") -> str:
    """Load the user's custom prompt. Returns empty string if not set."""
    path = _user_prompt_path(user_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_user_prompt(user_id: str, prompt: str) -> None:
    """Save the user's custom prompt to disk (atomic write via temp file + rename)."""
    import tempfile

    path = _user_prompt_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(prompt.strip(), encoding="utf-8")
    tmp.rename(path)
