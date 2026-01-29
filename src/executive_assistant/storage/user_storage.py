"""User-specific storage paths for prompts, skills, and MCP configs.

This module provides centralized path management for all user-scoped data,
ensuring consistent path construction across the codebase.
"""

from pathlib import Path

from executive_assistant.config.settings import settings


class UserPaths:
    """Centralized path management for user-scoped data.

    All user data is organized under: data/users/{thread_id}/

    Directory structure:
        data/users/{thread_id}/
        ├── prompts/          # User prompts
        │   └── prompt.md
        ├── skills/           # User skills
        │   └── on_demand/
        │       └── *.md
        ├── mcp/              # User MCP configs
        │   ├── local.json
        │   └── remote.json
        ├── files/            # (existing - file sandbox)
        ├── tdb/              # (existing - transactional DB)
        └── vdb/              # (existing - vector DB)
    """

    @staticmethod
    def get_user_root(thread_id: str) -> Path:
        """Get the root directory for a specific user/thread.

        Args:
            thread_id: Thread identifier (e.g., "telegram:123456")

        Returns:
            Path to user root directory: data/users/{thread_id}/
        """
        return settings.USERS_ROOT / thread_id

    @staticmethod
    def get_prompts_dir(thread_id: str) -> Path:
        """Get the prompts directory for a specific user.

        Args:
            thread_id: Thread identifier

        Returns:
            Path to prompts directory: data/users/{thread_id}/prompts/
        """
        return UserPaths.get_user_root(thread_id) / "prompts"

    @staticmethod
    def get_prompt_path(thread_id: str) -> Path:
        """Get the path to the user's prompt file.

        Args:
            thread_id: Thread identifier

        Returns:
            Path to prompt.md: data/users/{thread_id}/prompts/prompt.md
        """
        return UserPaths.get_prompts_dir(thread_id) / "prompt.md"

    @staticmethod
    def get_skills_root(thread_id: str) -> Path:
        """Get the skills root directory for a specific user.

        Args:
            thread_id: Thread identifier

        Returns:
            Path to skills directory: data/users/{thread_id}/skills/
        """
        return UserPaths.get_user_root(thread_id) / "skills"

    @staticmethod
    def get_skills_on_demand_dir(thread_id: str) -> Path:
        """Get the on-demand skills directory for a specific user.

        Args:
            thread_id: Thread identifier

        Returns:
            Path to on-demand skills: data/users/{thread_id}/skills/on_demand/
        """
        return UserPaths.get_skills_root(thread_id) / "on_demand"

    @staticmethod
    def get_skill_path(thread_id: str, skill_name: str) -> Path:
        """Get the path to a specific user skill file.

        Args:
            thread_id: Thread identifier
            skill_name: Name of the skill (will be normalized to snake_case.md)

        Returns:
            Path to skill file: data/users/{thread_id}/skills/on_demand/{skill_name}.md
        """
        # Normalize skill name to filename (snake_case)
        normalized_name = skill_name.lower().replace(" ", "_").replace("-", "_")
        return UserPaths.get_skills_on_demand_dir(thread_id) / f"{normalized_name}.md"

    @staticmethod
    def get_mcp_dir(thread_id: str) -> Path:
        """Get the MCP config directory for a specific user.

        Args:
            thread_id: Thread identifier

        Returns:
            Path to MCP directory: data/users/{thread_id}/mcp/
        """
        return UserPaths.get_user_root(thread_id) / "mcp"

    @staticmethod
    def get_mcp_local_path(thread_id: str) -> Path:
        """Get the path to the user's local MCP config file.

        Local MCP = stdio servers (command-line based)

        Args:
            thread_id: Thread identifier

        Returns:
            Path to local.json: data/users/{thread_id}/mcp/local.json
        """
        return UserPaths.get_mcp_dir(thread_id) / "local.json"

    @staticmethod
    def get_mcp_remote_path(thread_id: str) -> Path:
        """Get the path to the user's remote MCP config file.

        Remote MCP = HTTP/SSE servers (connectors)

        Args:
            thread_id: Thread identifier

        Returns:
            Path to remote.json: data/users/{thread_id}/mcp/remote.json
        """
        return UserPaths.get_mcp_dir(thread_id) / "remote.json"

    @staticmethod
    def ensure_user_dirs(thread_id: str) -> None:
        """Ensure all user directories exist.

        Creates the directory structure for a user if it doesn't exist:
        - data/users/{thread_id}/
        - data/users/{thread_id}/prompts/
        - data/users/{thread_id}/skills/on_demand/
        - data/users/{thread_id}/mcp/

        Args:
            thread_id: Thread identifier
        """
        UserPaths.get_prompts_dir(thread_id).mkdir(parents=True, exist_ok=True)
        UserPaths.get_skills_on_demand_dir(thread_id).mkdir(parents=True, exist_ok=True)
        UserPaths.get_mcp_dir(thread_id).mkdir(parents=True, exist_ok=True)


def get_thread_id_from_path(path: Path) -> str | None:
    """Extract thread_id from a user-scoped path.

    Args:
        path: A path within data/users/{thread_id}/

    Returns:
        The thread_id if the path is user-scoped, None otherwise.

    Examples:
        >>> get_thread_id_from_path(Path("data/users/telegram:123456/prompts/prompt.md"))
        "telegram:123456"
        >>> get_thread_id_from_path(Path("data/shared/files/test.txt"))
        None
    """
    try:
        # Check if path is under USERS_ROOT
        if not path.is_absolute():
            path = Path.cwd() / path

        # Resolve relative path from USERS_ROOT
        relative = path.relative_to(settings.USERS_ROOT)
        parts = relative.parts

        # First part should be thread_id
        if parts:
            return parts[0]
    except (ValueError, IndexError):
        # Path not under USERS_ROOT or no parts
        pass

    return None
