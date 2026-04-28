"""Deployment-aware data path resolution.

Two deployment modes:
- solo: Single user on desktop (.dmg) or server. user_id defaults to "default_user".
  data/users/default_user/ contains all personal data.
- team: Multiple users on one server. Each user gets data/users/{user_id}/.
  data/teams/{team_id}/ contains shared team data (server read-write).

See PLAN.md and ARCHITECTURE.md for design rationale.
"""

from pathlib import Path

from src.config import get_settings

DEFAULT_USER_ID = "default_user"


class DataPaths:
    """Resolves data paths based on deployment mode and user identity.

    In solo mode: data/users/default_user/ (single user, default identity)
    In team mode: data/users/{user_id}/ (per-user isolation, same server)

    Team data is stored at data/teams/{team_id}/ and accessed via team_* methods.
    Team paths return None when team_id is not set (solo mode).
    """

    def __init__(
        self,
        deployment: str | None = None,
        data_path: str | None = None,
        user_id: str | None = None,
        team_id: str | None = None,
    ):
        settings = get_settings()
        self.deployment = deployment or settings.deployment
        self.base = Path(data_path or settings.data_path or "data")
        self.user_id = user_id or DEFAULT_USER_ID
        self.team_id = team_id
        self.base.mkdir(parents=True, exist_ok=True)

    # -- Per-user base directory --

    def _user_base(self) -> Path:
        """Base directory for the current user: data/users/{user_id}/"""
        p = self.base / "users" / self.user_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    # -- Personal data (per-user, read-write) --

    @property
    def user_dir(self) -> Path:
        """Root of user data: data/users/{user_id}/"""
        return self._user_base()

    def conversation_dir(self) -> Path:
        p = self._user_base() / "conversation"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def memory_dir(self) -> Path:
        p = self._user_base() / "memory"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def email_dir(self) -> Path:
        p = self._user_base() / "email"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def gmail_cache(self) -> Path:
        p = self._user_base() / "gmail_cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def contacts_dir(self) -> Path:
        p = self._user_base() / "contacts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def todos_dir(self) -> Path:
        p = self._user_base() / "todos"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def workspace_dir(self) -> Path:
        settings = get_settings()
        if settings.filesystem.workspace_root:
            p = Path(settings.filesystem.workspace_root).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        # Default for single-user desktop: ~/Executive Assistant/
        p = Path.home() / "Executive Assistant"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def skills_dir(self) -> Path:
        p = self._user_base() / "skills"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def subagents_dir(self) -> Path:
        p = self._user_base() / "subagents"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def agent_defs_dir(self) -> Path:
        p = self._user_base() / "subagents" / "agent_defs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def work_queue_db(self) -> Path:
        return self.subagents_dir() / "work_queue.db"

    def apps_dir(self) -> Path:
        p = self._user_base() / "apps"
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
        return self._user_base() / ".mcp.json"

    def workspace_cache(self) -> Path:
        return self.workspace_dir() / ".file_cache.json"

    # -- Versions --

    def versions_dir(self) -> Path:
        p = self.workspace_dir() / ".versions"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # -- Templates --

    @property
    def templates(self) -> Path:
        return self.base / "templates"

    def template_path(self, name: str) -> Path:
        return self.templates / f"{name}.json"

    # -- Team data (returns None if team_id not set, i.e. solo mode) --

    def team_dir(self) -> Path | None:
        """Root of team data: data/teams/{team_id}/. None in solo mode."""
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id

    def team_skills_dir(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "skills"

    def team_apps_dir(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "apps"

    def team_contacts_dir(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "contacts"

    def team_todos_dir(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "todos"

    def team_memory_dir(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "memory"

    def team_files_dir(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "files"

    def team_mcp_config_path(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / ".mcp.json"

    def team_config_path(self) -> Path | None:
        if not self.team_id:
            return None
        return self.base / "teams" / self.team_id / "config.yaml"

    # -- Shared data (legacy, will be removed in Phase 8 folder cleanup) --

    @property
    def shared(self) -> Path:
        """Legacy shared directory. Use team_* methods instead."""
        return self.base / "shared"

    def shared_apps_dir(self) -> Path:
        """Legacy. Use team_apps_dir() instead."""
        p = self.shared / "apps"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # -- Backwards compat: 'private' property redirects to user_dir --

    @property
    def private(self) -> Path:
        """Backwards compat: returns data/users/{user_id}/ (was data/private/)."""
        return self._user_base()

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


_paths_cache: dict[str, DataPaths] = {}


def get_paths(user_id: str | None = None, team_id: str | None = None) -> DataPaths:
    """Get DataPaths instance (cached per user_id+team_id pair).

    In solo mode: user_id defaults to "default_user", team_id is None.
    In team mode: user_id comes from auth (JWT), team_id from config.
    """
    uid = user_id or DEFAULT_USER_ID
    tid = team_id  # None for solo mode
    cache_key = f"{uid}:{tid or ''}"

    if cache_key not in _paths_cache:
        _paths_cache[cache_key] = DataPaths(user_id=uid, team_id=tid)

    return _paths_cache[cache_key]
