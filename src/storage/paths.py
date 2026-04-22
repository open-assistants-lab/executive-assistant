"""Deployment-aware data path resolution.

Two deployment modes:
- solo: Single user on desktop (.dmg). Container IS the isolation boundary.
- multi-user: Docker container per user, org gets many containers.
  data/shared/ is a mounted volume for collaborative apps.

Both modes use the same code and the same paths. The container serves
exactly one user — no per-user subdirectory needed.

See DATA_ARCHITECTURE.md for design rationale.
"""

from pathlib import Path

from src.config import get_settings


class DataPaths:
    """Resolves data paths based on deployment mode."""

    def __init__(
        self,
        deployment: str | None = None,
        data_path: str | None = None,
        user_id: str | None = None,
    ):
        settings = get_settings()
        self.deployment = deployment or settings.deployment
        self.base = Path(data_path or settings.data_path or "data")
        self.user_id = user_id or "default"
        self.base.mkdir(parents=True, exist_ok=True)

    # -- Top-level directories --

    @property
    def private(self) -> Path:
        return self.base / "private"

    @property
    def shared(self) -> Path:
        return self.base / "shared"

    @property
    def templates(self) -> Path:
        return self.base / "templates"

    # -- Private data (container-local) --

    def conversation_dir(self) -> Path:
        p = self.private / "conversation"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def memory_dir(self) -> Path:
        p = self.private / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def email_dir(self) -> Path:
        p = self.private / "email"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def contacts_dir(self) -> Path:
        p = self.private / "contacts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def todos_dir(self) -> Path:
        p = self.private / "todos"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def workspace_dir(self) -> Path:
        p = self.private / "workspace"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def skills_dir(self) -> Path:
        p = self.private / "skills"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def subagents_dir(self) -> Path:
        p = self.private / "subagents"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def work_queue_db(self) -> Path:
        return self.subagents_dir() / "work_queue.db"

    def apps_dir(self) -> Path:
        p = self.private / "apps"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # -- Shared data (org-wide, mounted volume in multi-user) --

    def shared_apps_dir(self) -> Path:
        p = self.shared / "apps"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # -- Convenience: DB file paths --

    def conversation_db(self) -> Path:
        return self.conversation_dir() / "messages.db"

    def email_db(self) -> Path:
        return self.email_dir() / "emails.db"

    def contacts_db(self) -> Path:
        return self.contacts_dir() / "contacts.db"

    def todos_db(self) -> Path:
        return self.todos_dir() / "todos.db"

    def memory_db(self) -> Path:
        return self.memory_dir() / "memory.db"

    def mcp_config_path(self) -> Path:
        return self.private / ".mcp.json"

    def workspace_cache(self) -> Path:
        return self.workspace_dir() / ".file_cache.json"

    # -- Versions --

    def versions_dir(self) -> Path:
        p = self.workspace_dir() / ".versions"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # -- Templates --

    def template_path(self, name: str) -> Path:
        return self.templates / f"{name}.json"

    # -- System paths (not user-scoped) --

    def model_cache_path(self) -> Path:
        p = self.base / "cache"
        p.mkdir(parents=True, exist_ok=True)
        return p / "models.json"

    def logs_dir(self) -> Path:
        p = self.base / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def traces_path(self) -> Path:
        p = self.base / "traces"
        p.mkdir(parents=True, exist_ok=True)
        return p / "traces.jsonl"

    def jobs_db_path(self) -> Path:
        return self.base / "jobs.db"

    def jobs_results_db_path(self) -> Path:
        return self.base / "jobs_results.db"


_paths: DataPaths | None = None


def get_paths(user_id: str | None = None) -> DataPaths:
    """Get DataPaths singleton (optionally for a specific user)."""
    global _paths
    if _paths is None or (user_id is not None and _paths.user_id != user_id):
        _paths = DataPaths(user_id=user_id)
    return _paths
