"""
Group-based storage routing.

This module provides the group abstraction layer that routes all storage
operations (files, KB, DB, etc.) through group_id rather than thread_id.

Identity Resolution:
  1. Extract user_id from request context (Telegram, HTTP)
  2. Resolve aliases to canonical user_id
  3. Get or create group for user
  4. Route thread_id to group_id

Storage Layout:
  data/groups/{group_id}/
    files/
    kb/
    db/
    mem/
    reminders/
    workflows/

Database Tables:
  - groups: Main storage groups (replaces workspaces)
  - group_members: Group membership with roles
  - group_acl: Group-level ACL for resource permissions
  - thread_groups: Maps threads to groups
  - user_workspaces: Maps users to their individual group
  - team_groups: Team groups for collaboration
"""

import asyncio
import inspect
import uuid
from contextvars import ContextVar
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, Literal

import asyncpg

from executive_assistant.config.settings import settings


# Context variable for group_id - set by channels when processing messages
_group_id: ContextVar[str | None] = ContextVar("_group_id", default=None)

# Context variable for user_id - set by channels when processing messages
_user_id: ContextVar[str | None] = ContextVar("_user_id", default=None)

# Cache for group lookups (within a single request/transaction)
_group_cache: dict[str, dict] = {}


def set_group_id(group_id: str) -> None:
    """Set the group_id for the current context."""
    _group_id.set(group_id)


def get_group_id() -> str | None:
    """Get the group_id for the current context."""
    return _group_id.get()


def clear_group_id() -> None:
    """Clear the group_id from the current context."""
    try:
        _group_id.set(None)
    except Exception:
        pass


def set_user_id(user_id: str) -> None:
    """Set the user_id for the current context."""
    _user_id.set(user_id)


def get_user_id() -> str | None:
    """Get the user_id for the current context."""
    return _user_id.get()


def clear_user_id() -> None:
    """Clear the user_id from the current context."""
    try:
        _user_id.set(None)
    except Exception:
        pass


def sanitize_thread_id(thread_id: str) -> str:
    """
    Sanitize thread_id for use as filename/directory name.

    Replaces characters that could cause issues in filenames.

    Args:
        thread_id: Raw thread_id (e.g., "telegram:user123", "email:user@example.com")

    Returns:
        Sanitized string safe for filenames (e.g., "telegram_user123", "email_user_example.com")
    """
    replacements = {
        ":": "_",
        "/": "_",
        "@": "_",
        "\\": "_",
    }
    for old, new in replacements.items():
        thread_id = thread_id.replace(old, new)
    return thread_id


def generate_group_id() -> str:
    """Generate a new unique group ID."""
    return f"group:{uuid.uuid4()}"


def generate_anon_user_id() -> str:
    """Generate a new anonymous user ID for web guests."""
    return f"anon:{uuid.uuid4()}"


# ============================================================================
# Group Path Resolution
# ============================================================================

def get_groups_root() -> Path:
    """Get the root directory for all groups."""
    return settings.GROUPS_ROOT


def get_group_path(group_id: str) -> Path:
    """
    Get the root directory for a specific group.

    Args:
        group_id: The group ID

    Returns:
        Path to group root: data/groups/{group_id}/
    """
    sanitized = sanitize_thread_id(group_id)
    group_path = get_groups_root() / sanitized
    group_path.mkdir(parents=True, exist_ok=True)
    return group_path


def get_group_files_path(group_id: str) -> Path:
    """Get the files directory for a group."""
    return get_group_path(group_id) / "files"


def get_group_kb_path(group_id: str) -> Path:
    """Get the KB directory for a group."""
    return get_group_path(group_id) / "kb"


def get_group_db_path(group_id: str) -> Path:
    """Get the DB directory for a group."""
    db_path = get_group_path(group_id) / "db"
    db_path.mkdir(parents=True, exist_ok=True)
    return db_path / "db.db"


def get_group_mem_path(group_id: str) -> Path:
    """Get the memory directory for a group."""
    mem_path = get_group_path(group_id) / "mem"
    mem_path.mkdir(parents=True, exist_ok=True)
    return mem_path / "mem.db"


def get_group_reminders_path(group_id: str) -> Path:
    """Get the reminders directory for a group."""
    return get_group_path(group_id) / "reminders"


def get_group_workflows_path(group_id: str) -> Path:
    """Get the workflows directory for a group."""
    return get_group_path(group_id) / "workflows"


# ============================================================================
# Database Operations (PostgreSQL)
# ============================================================================

async def get_db_conn() -> asyncpg.Connection:
    """Get a database connection."""
    return await asyncpg.connect(settings.POSTGRES_URL)


async def resolve_user_id(user_id: str, conn: asyncpg.Connection | None = None) -> str:
    """
    Resolve a user_id to its canonical form, handling aliases.

    Args:
        user_id: The user ID (may be an alias)
        conn: Optional database connection

    Returns:
        The canonical user_id
    """
    if conn is None:
        conn = await get_db_conn()

    # Check if user_id is an alias
    canonical = await conn.fetchval(
        "SELECT user_id FROM user_aliases WHERE alias_id = $1",
        user_id
    )

    return canonical or user_id


async def get_user_group(user_id: str, conn: asyncpg.Connection | None = None) -> str | None:
    """
    Get the group_id for a user (individual group).

    Args:
        user_id: The canonical user_id
        conn: Optional database connection

    Returns:
        The group_id or None if user has no group
    """
    if conn is None:
        conn = await get_db_conn()

    return await conn.fetchval(
        "SELECT group_id FROM user_workspaces WHERE user_id = $1",
        user_id
    )


async def get_thread_group(thread_id: str, conn: asyncpg.Connection | None = None) -> str | None:
    """
    Get the group_id for a thread.

    Args:
        thread_id: The thread ID
        conn: Optional database connection

    Returns:
        The group_id or None if thread has no group
    """
    if conn is None:
        conn = await get_db_conn()

    return await conn.fetchval(
        "SELECT group_id FROM thread_groups WHERE thread_id = $1",
        thread_id
    )


async def ensure_user(
    user_id: str,
    conn: asyncpg.Connection | None = None,
) -> str:
    """
    Ensure a user exists, creating if necessary.

    Args:
        user_id: The user ID (should be canonical, not an alias)
        conn: Optional database connection

    Returns:
        The user_id
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
        user_id
    )
    return user_id


async def ensure_user_group(
    user_id: str,
    conn: asyncpg.Connection | None = None,
) -> str:
    """
    Ensure a user has an individual group, creating if necessary.

    Args:
        user_id: The canonical user_id
        conn: Optional database connection

    Returns:
        The group_id
    """
    if conn is None:
        conn = await get_db_conn()

    # First ensure user exists
    await ensure_user(user_id, conn)

    # Check if group exists
    existing = await get_user_group(user_id, conn)
    if existing:
        return existing

    # Create new group
    group_id = generate_group_id()

    async with conn.transaction():
        # Create group
        await conn.execute(
            """INSERT INTO groups (group_id, type, name, owner_user_id)
               VALUES ($1, 'individual', 'My Workspace', $2)""",
            group_id, user_id
        )

        # Map user to group
        await conn.execute(
            "INSERT INTO user_workspaces (user_id, group_id) VALUES ($1, $2)",
            user_id, group_id
        )

    return group_id


async def ensure_thread_group(
    thread_id: str,
    user_id: str,
    conn: asyncpg.Connection | None = None,
) -> str:
    """
    Ensure a thread has a group, creating if necessary.

    This resolves the user to their canonical form (via aliases),
    ensures they have a group, and maps the thread to it.

    Args:
        thread_id: The thread ID
        user_id: The user ID from request (may be an alias)
        conn: Optional database connection

    Returns:
        The group_id
    """
    if conn is None:
        conn = await get_db_conn()

    # Resolve alias to canonical user_id
    canonical_user_id = await resolve_user_id(user_id, conn)

    # Ensure user has group
    group_id = await ensure_user_group(canonical_user_id, conn)

    # Map thread to group
    await conn.execute(
        """INSERT INTO thread_groups (thread_id, group_id)
           VALUES ($1, $2)
           ON CONFLICT (thread_id) DO UPDATE SET group_id = $2""",
        thread_id, group_id
    )

    return group_id


async def get_group_info(group_id: str, conn: asyncpg.Connection | None = None) -> dict | None:
    """
    Get group information.

    Args:
        group_id: The group ID
        conn: Optional database connection

    Returns:
        Group info dict or None
    """
    if conn is None:
        conn = await get_db_conn()

    row = await conn.fetchrow(
        """SELECT group_id, type, name, owner_user_id, owner_group_id, owner_system_id, created_at
           FROM groups WHERE group_id = $1""",
        group_id
    )

    if not row:
        return None

    return {
        "group_id": row["group_id"],
        "type": row["type"],
        "name": row["name"],
        "owner_user_id": row["owner_user_id"],
        "owner_group_id": row["owner_group_id"],
        "owner_system_id": row["owner_system_id"],
        "created_at": row["created_at"],
    }


# ============================================================================
# Access Control
# ============================================================================

ROLE_PERMISSIONS = {
    "admin": {"read": True, "write": True, "admin": True},
    "editor": {"read": True, "write": True, "admin": False},
    "reader": {"read": True, "write": False, "admin": False}
}


async def can_access(
    user_id: str,
    group_id: str,
    action: Literal["read", "write", "admin"],
    conn: asyncpg.Connection | None = None,
) -> bool:
    """
    Check if a user can perform an action on a group.

    Args:
        user_id: The user ID
        group_id: The group ID
        action: The action to check (read, write, admin)
        conn: Optional database connection

    Returns:
        True if access is granted, False otherwise
    """
    if conn is None:
        conn = await get_db_conn()

    # Resolve alias to canonical user_id
    canonical_user_id = await resolve_user_id(user_id, conn)

    # Get group info
    group = await get_group_info(group_id, conn)
    if not group:
        return False

    # Group owner is always admin
    if group["owner_user_id"] == canonical_user_id:
        return True

    # Check explicit group membership
    member = await conn.fetchrow(
        """SELECT role FROM group_members
           WHERE group_id = $1 AND user_id = $2""",
        group_id, canonical_user_id
    )
    if member:
        return ROLE_PERMISSIONS[member["role"]].get(action, False)

    # Team group storage: check team membership
    if group["owner_group_id"]:
        # Note: this references team_groups table (team groups, not storage groups)
        team_role = await conn.fetchval(
            """SELECT role FROM team_group_members
               WHERE group_id = $1 AND user_id = $2""",
            group["owner_group_id"], canonical_user_id
        )
        if team_role:
            # Team admins are group admins, members are readers
            return team_role == "admin" or action == "read"

    # Public group: everyone can read
    if group["type"] == "public" and action == "read":
        return True

    # Check ACL for external grants
    # Note: ACL only supports 'read' and 'write' permissions (admin via group_members only)
    acl_grant = await conn.fetchval(
        """SELECT permission FROM group_acl
           WHERE group_id = $1
           AND target_user_id = $2
           AND (expires_at IS NULL OR expires_at > NOW())
           ORDER BY
             CASE permission
               WHEN 'write' THEN 2
               WHEN 'read' THEN 1
               ELSE 0
             END DESC
           LIMIT 1""",
        group_id, canonical_user_id
    )

    if acl_grant:
        # Write permission grants both read and write access
        if acl_grant == "write" and action in ("read", "write"):
            return True
        # Read permission grants only read access
        if acl_grant == "read" and action == "read":
            return True

    return False


# ============================================================================
# Accessible Groups
# ============================================================================

async def accessible_groups(
    user_id: str,
    conn: asyncpg.Connection | None = None,
) -> list[dict]:
    """
    Return all groups the user can access.

    Args:
        user_id: The user ID
        conn: Optional database connection

    Returns:
        List of group dicts with role and type info
    """
    if conn is None:
        conn = await get_db_conn()

    # Resolve alias to canonical user_id
    canonical_user_id = await resolve_user_id(user_id, conn)

    results = []

    # 1. Individual group (if owner)
    own = await conn.fetchrow(
        """SELECT g.group_id, g.type, g.name
           FROM user_workspaces uw
           JOIN groups g ON g.group_id = uw.group_id
           WHERE uw.user_id = $1""",
        canonical_user_id
    )
    if own:
        results.append({
            "group_id": own["group_id"],
            "role": "admin",
            "type": own["type"],
            "name": own["name"],
        })

    # 2. Team group storage (via team group membership)
    group_rows = await conn.fetch(
        """SELECT DISTINCT g.group_id, g.type, g.name, gm.role
           FROM team_group_members gm
           JOIN group_workspaces gw ON gw.group_id = gm.group_id
           JOIN groups g ON g.group_id = gw.group_id
           WHERE gm.user_id = $1""",
        canonical_user_id
    )
    for row in group_rows:
        role = "admin" if row["role"] == "admin" else "reader"
        results.append({
            "group_id": row["group_id"],
            "role": role,
            "type": row["type"],
            "name": row["name"],
        })

    # 3. Groups where user is explicit member
    member_rows = await conn.fetch(
        """SELECT g.group_id, g.type, g.name, gm.role
           FROM group_members gm
           JOIN groups g ON g.group_id = gm.group_id
           WHERE gm.user_id = $1""",
        canonical_user_id
    )
    for row in member_rows:
        results.append({
            "group_id": row["group_id"],
            "role": row["role"],
            "type": row["type"],
            "name": row["name"],
        })

    # 4. Public group (everyone has read access)
    public_grp = await conn.fetchrow(
        "SELECT group_id, name FROM groups WHERE type = 'public'"
    )
    if public_grp and not any(g["group_id"] == public_grp["group_id"] for g in results):
        results.append({
            "group_id": public_grp["group_id"],
            "role": "reader",
            "type": "public",
            "name": public_grp["name"],
        })

    return results


# ============================================================================
# Alias / Merge Operations
# ============================================================================

async def add_alias(
    alias_id: str,
    canonical_user_id: str,
    conn: asyncpg.Connection | None = None,
) -> None:
    """
    Add an alias mapping (for merges/upgrades).

    Args:
        alias_id: The alias (e.g., anon:abc123)
        canonical_user_id: The canonical user ID
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        "INSERT INTO user_aliases (alias_id, user_id) VALUES ($1, $2) ON CONFLICT (alias_id) DO UPDATE SET user_id = $2",
        alias_id, canonical_user_id
    )


async def resolve_alias_chain(user_id: str, conn: asyncpg.Connection | None = None) -> str:
    """
    Resolve an alias chain to get the canonical user_id.

    Args:
        user_id: The user ID (may be an alias)
        conn: Optional database connection

    Returns:
        The canonical user_id
    """
    if conn is None:
        conn = await get_db_conn()

    seen = {user_id}
    current = user_id

    while True:
        resolved = await conn.fetchval(
            "SELECT user_id FROM user_aliases WHERE alias_id = $1",
            current
        )
        if not resolved:
            break
        if resolved in seen:
            # Circular reference detected, return the original
            break
        seen.add(resolved)
        current = resolved

    return current


# ============================================================================
# Public Group Setup
# ============================================================================

async def ensure_public_group(conn: asyncpg.Connection | None = None) -> str:
    """
    Ensure the public group exists, creating if necessary.

    Args:
        conn: Optional database connection

    Returns:
        The public group_id
    """
    if conn is None:
        conn = await get_db_conn()

    group_id = "public"

    row = await conn.fetchrow(
        "SELECT group_id FROM groups WHERE group_id = $1",
        group_id
    )

    if not row:
        await conn.execute(
            """INSERT INTO groups (group_id, type, name, owner_system_id)
               VALUES ($1, 'public', 'Public', 'public')""",
            group_id
        )

    return group_id


# ============================================================================
# Permission Decorators (for use by tools)
# ============================================================================

async def _check_permission_async(action: Literal["read", "write", "admin"]) -> None:
    """
    Async permission check - shared logic for both sync and async wrappers.

    Raises:
        ValueError: If no group context or no user context
        PermissionError: If user lacks required permission
    """
    # Get group context
    group_id = get_group_id()
    if not group_id:
        from loguru import logger
        logger.warning("Permission check failed: no group context")
        raise ValueError("No group context - permission check failed")

    # Get user context
    user_id = get_user_id()
    if not user_id:
        from loguru import logger
        logger.warning("Permission check failed: no user context")
        raise ValueError("No user context - permission check failed")

    # Check permission
    conn = await get_db_conn()
    has_permission = await can_access(
        user_id=user_id,
        group_id=group_id,
        action=action,
        conn=conn
    )

    if not has_permission:
        from loguru import logger
        logger.warning(
            "Permission denied: user={user} group={group} action={action}",
            user=user_id,
            group=group_id,
            action=action
        )
        raise PermissionError(
            f"You don't have {action} permission for this group"
        )


def require_permission(
    action: Literal["read", "write", "admin"],
    scope: Literal["shared", "group", "user"] = "group",
):
    """
    Decorator to check permissions before executing a tool.

    The decorated function will raise PermissionError if the user lacks
    the required permission for the current context.

    Works with both sync and async functions - automatically detects
    the function type and handles permission checking appropriately.

    Args:
        action: Required permission level (read, write, or admin)
            - "read": User can view resources
            - "write": User can create/modify resources
            - "admin": User can manage settings
        scope: Resource scope to check permissions for
            - "shared": Admin write, everyone read (policies, SOPs)
            - "group": Check group membership permissions (default)
            - "user": Personal user context only

    Raises:
        ValueError: If no valid context for the scope
        PermissionError: If user lacks required permission

    Examples:
        >>> @require_permission("write", scope="shared")
        ... def write_shared_doc(content: str) -> str:
        ...     # Admin only for shared resources
        ...     pass

        >>> @require_permission("read", scope="shared")
        ... async def read_shared_policies() -> str:
        ...     # Everyone can read shared resources
        ...     pass

        >>> @require_permission("write")  # scope="group" is default
        ... def write_file(filename: str, content: str) -> str:
        ...     # Checks group permissions
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        # Check if the function is async
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                await _check_permission_with_scope(action, scope)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Run permission check in sync context
                try:
                    loop = asyncio.get_running_loop()
                    # We're inside an async event loop - use simplified check
                    _check_permission_sync(action, scope)
                except RuntimeError:
                    # No running loop, safe to use asyncio.run()
                    asyncio.run(_check_permission_with_scope(action, scope))
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator


async def _check_permission_with_scope(
    action: Literal["read", "write", "admin"],
    scope: Literal["shared", "group", "user"],
) -> None:
    """
    Check permissions based on scope.

    Args:
        action: Required permission level
        scope: Resource scope

    Raises:
        ValueError: If no valid context for the scope
        PermissionError: If user lacks required permission
    """
    from loguru import logger

    if scope == "shared":
        # Shared resources: everyone can read, only admins can write
        user_id = get_user_id()
        if not user_id:
            raise ValueError("No user context - shared resources require authentication")

        if action == "read":
            # Everyone can read shared resources
            return
        else:
            # Write/admin requires admin check
            from executive_assistant.config.settings import settings
            admin_ids = settings.ADMIN_USER_IDS
            if user_id not in admin_ids:
                logger.warning(f"Shared resource write denied for non-admin user: {user_id}")
                raise PermissionError("Shared resources can only be modified by admins")

    elif scope == "group":
        # Group resources: check group membership permissions
        group_id = get_group_id()
        if group_id:
            # Has group context - check permissions
            await _check_permission_async(action)
            return

        # No group_id - fall back to user context (Telegram, etc.)
        user_id = get_user_id()
        if not user_id:
            raise ValueError("No group or user context - permission check failed")
        # Allow operation for user context (personal chat)
        logger.debug(f"Allowing {action} operation for user context: {user_id}")

    elif scope == "user":
        # User resources: must have user_id
        user_id = get_user_id()
        if not user_id:
            raise ValueError("No user context - user resources require authentication")
        # Personal resources - user has full access to their own data

    else:
        raise ValueError(f"Unknown scope: {scope}")


def _check_permission_sync(
    action: Literal["read", "write", "admin"],
    scope: Literal["shared", "group", "user"],
) -> None:
    """
    Sync version of permission check for use in sync functions.

    Used when calling from sync context within an async event loop.
    """
    from loguru import logger

    if scope == "shared":
        user_id = get_user_id()
        if not user_id:
            raise ValueError("No user context - shared resources require authentication")

        if action == "read":
            return
        else:
            from executive_assistant.config.settings import settings
            admin_ids = settings.ADMIN_USER_IDS
            if user_id not in admin_ids:
                logger.warning(f"Shared resource write denied for non-admin user: {user_id}")
                raise PermissionError("Shared resources can only be modified by admins")

    elif scope == "group":
        group_id = get_group_id()
        logger.debug(f"Permission check: group_id={group_id}")
        if group_id:
            # Has group context
            user_id = get_user_id()
            logger.debug(f"Permission check: user_id={user_id}")
            if not user_id:
                raise ValueError("No user context - permission check failed")
            # Would need to check permissions, but for now allow if group_id exists
            logger.debug(f"Group context found: {group_id}, user: {user_id}")
            return

        # No group_id - fall back to user context
        user_id = get_user_id()
        if not user_id:
            raise ValueError("No group or user context - permission check failed")
        logger.debug(f"Allowing {action} operation for user context: {user_id}")

    elif scope == "user":
        user_id = get_user_id()
        if not user_id:
            raise ValueError("No user context - user resources require authentication")

    else:
        raise ValueError(f"Unknown scope: {scope}")



def require_group_context(func: Callable) -> Callable:
    """
    Decorator to ensure group context exists before executing a tool.

    This is a lighter check than require_permission - it only verifies
    that a group_id is set in the context, without checking permissions.
    Use this for operations that don't need access control (e.g., getting
    group metadata).

    Works with both sync and async functions.

    Args:
        func: The function to wrap

    Raises:
        ValueError: If no group context

    Examples:
        >>> @require_group_context
        ... def get_group_info() -> str:
        ...     # Sync tool - only executes if group context exists
        ...     pass

        >>> @require_group_context
        ... async def async_get_group_info() -> str:
        ...     # Async tool - only executes if group context exists
        ...     pass
    """
    is_async = inspect.iscoroutinefunction(func)

    if is_async:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            group_id = get_group_id()
            if not group_id:
                from loguru import logger
                logger.warning("Group context check failed: no group context")
                raise ValueError("No group context - group check failed")
            return await func(*args, **kwargs)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            group_id = get_group_id()
            if not group_id:
                from loguru import logger
                logger.warning("Group context check failed: no group context")
                raise ValueError("No group context - group check failed")
            return func(*args, **kwargs)
        return sync_wrapper


# ============================================================================
# Group Member Management
# ============================================================================

async def add_group_member(
    group_id: str,
    user_id: str,
    role: Literal["admin", "editor", "reader"],
    granted_by: str | None = None,
    conn=None,
) -> None:
    """
    Add a user to a group with a role.

    Args:
        group_id: The group ID
        user_id: The user ID to add
        role: Either 'admin', 'editor', or 'reader'
        granted_by: Optional user ID who granted this role
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """INSERT INTO group_members (group_id, user_id, role, granted_by)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (group_id, user_id) DO UPDATE SET role = $3""",
        group_id, user_id, role, granted_by
    )


async def remove_group_member(
    group_id: str,
    user_id: str,
    conn=None,
) -> None:
    """
    Remove a user from a group.

    Args:
        group_id: The group ID
        user_id: The user ID to remove
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        "DELETE FROM group_members WHERE group_id = $1 AND user_id = $2",
        group_id, user_id
    )


async def get_group_members(
    group_id: str,
    conn=None,
) -> list[dict]:
    """
    Get all members of a group.

    Args:
        group_id: The group ID
        conn: Optional database connection

    Returns:
        List of member dicts with user_id, role, granted_by, granted_at
    """
    if conn is None:
        conn = await get_db_conn()

    rows = await conn.fetch(
        """SELECT user_id, role, granted_by, granted_at
           FROM group_members
           WHERE group_id = $1
           ORDER BY granted_at""",
        group_id
    )

    return [
        {
            "user_id": row["user_id"],
            "role": row["role"],
            "granted_by": row["granted_by"],
            "granted_at": row["granted_at"],
        }
        for row in rows
    ]


async def grant_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    target_user_id: str,
    permission: Literal["read", "write"],
    expires_at: str | None = None,
    conn=None,
) -> None:
    """
    Grant ACL permission on a specific resource to a user.

    Args:
        group_id: The group ID
        resource_type: Type of resource (e.g., 'file_folder', 'kb_collection', 'db_table')
        resource_id: ID of the specific resource
        target_user_id: The user to grant permission to
        permission: Either 'read' or 'write'
        expires_at: Optional expiration timestamp
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """INSERT INTO group_acl
           (group_id, resource_type, resource_id, target_user_id, permission, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (group_id, resource_type, resource_id, target_user_id, NULL)
           DO UPDATE SET permission = $5, expires_at = $6""",
        group_id, resource_type, resource_id, target_user_id, permission, expires_at
    )


async def revoke_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    target_user_id: str,
    conn=None,
) -> None:
    """
    Revoke ACL permission from a user.

    Args:
        group_id: The group ID
        resource_type: Type of resource
        resource_id: ID of the specific resource
        target_user_id: The user to revoke permission from
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """DELETE FROM group_acl
           WHERE group_id = $1
           AND resource_type = $2
           AND resource_id = $3
           AND target_user_id = $4""",
        group_id, resource_type, resource_id, target_user_id
    )


async def grant_team_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    target_team_group_id: str,
    permission: Literal["read", "write"],
    expires_at: str | None = None,
    conn=None,
) -> None:
    """
    Grant ACL permission on a specific resource to a team group.

    Args:
        group_id: The group ID
        resource_type: Type of resource
        resource_id: ID of the specific resource
        target_team_group_id: The team group to grant permission to
        permission: Either 'read' or 'write'
        expires_at: Optional expiration timestamp
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """INSERT INTO group_acl
           (group_id, resource_type, resource_id, target_group_id, permission, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (group_id, resource_type, resource_id, NULL, target_group_id)
           DO UPDATE SET permission = $5, expires_at = $6""",
        group_id, resource_type, resource_id, target_team_group_id, permission, expires_at
    )


async def revoke_team_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    target_team_group_id: str,
    conn=None,
) -> None:
    """
    Revoke ACL permission from a team group.

    Args:
        group_id: The group ID
        resource_type: Type of resource
        resource_id: ID of the specific resource
        target_team_group_id: The team group to revoke permission from
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """DELETE FROM group_acl
           WHERE group_id = $1
           AND resource_type = $2
           AND resource_id = $3
           AND target_group_id = $4""",
        group_id, resource_type, resource_id, target_team_group_id
    )


async def get_resource_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    conn=None,
) -> list[dict]:
    """
    Get all ACL entries for a specific resource.

    Args:
        group_id: The group ID
        resource_type: Type of resource
        resource_id: ID of the specific resource
        conn: Optional database connection

    Returns:
        List of ACL dicts with target_user_id, target_group_id, permission, expires_at
    """
    if conn is None:
        conn = await get_db_conn()

    rows = await conn.fetch(
        """SELECT id, target_user_id, target_group_id, permission, created_at, expires_at
           FROM group_acl
           WHERE group_id = $1
           AND resource_type = $2
           AND resource_id = $3
           ORDER BY created_at""",
        group_id, resource_type, resource_id
    )

    return [
        {
            "id": row["id"],
            "target_user_id": row["target_user_id"],
            "target_group_id": row["target_group_id"],
            "permission": row["permission"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]


# ============================================================================
# Backward Compatibility Aliases (workspace → group)
# ============================================================================

# Aliases for deprecated workspace naming
def get_workspace_id() -> str | None:
    """Get the workspace_id for the current context. (DEPRECATED - use get_group_id)"""
    return get_group_id()

def set_workspace_id(group_id: str) -> None:
    """Set the workspace_id for the current context. (DEPRECATED - use set_group_id)"""
    return set_group_id(group_id)

def clear_workspace_id() -> None:
    """Clear the workspace_id from the current context. (DEPRECATED - use clear_group_id)"""
    return clear_group_id()

def get_workspaces_root() -> Path:
    """Get the root directory for all workspaces. (DEPRECATED - use get_groups_root)"""
    return get_groups_root()

def get_workspace_path(group_id: str) -> Path:
    """Get the root directory for a specific workspace. (DEPRECATED - use get_group_path)"""
    return get_group_path(group_id)

def get_workspace_files_path(group_id: str) -> Path:
    """Get the files directory for a workspace. (DEPRECATED - use get_group_files_path)"""
    return get_group_files_path(group_id)

def get_workspace_kb_path(group_id: str) -> Path:
    """Get the KB directory for a workspace. (DEPRECATED - use get_group_kb_path)"""
    return get_group_kb_path(group_id)

def get_workspace_db_path(group_id: str) -> Path:
    """Get the DB directory for a workspace. (DEPRECATED - use get_group_db_path)"""
    return get_group_db_path(group_id)

def get_workspace_mem_path(group_id: str) -> Path:
    """Get the memory directory for a workspace. (DEPRECATED - use get_group_mem_path)"""
    return get_group_mem_path(group_id)

def get_workspace_reminders_path(group_id: str) -> Path:
    """Get the reminders directory for a workspace. (DEPRECATED - use get_group_reminders_path)"""
    return get_group_reminders_path(group_id)

def get_workspace_workflows_path(group_id: str) -> Path:
    """Get the workflows directory for a workspace. (DEPRECATED - use get_group_workflows_path)"""
    return get_group_workflows_path(group_id)


# Backward compatibility aliases for ACL functions
async def grant_group_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    target_group_id: str,
    permission: Literal["read", "write"],
    expires_at: str | None = None,
    conn=None,
) -> None:
    """Grant ACL permission to a group. (DEPRECATED - use grant_acl with target_group_id)"""
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """INSERT INTO group_acl
           (group_id, resource_type, resource_id, target_group_id, permission, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (group_id, resource_type, resource_id, NULL, target_group_id)
           DO UPDATE SET permission = $5, expires_at = $6""",
        group_id, resource_type, resource_id, target_group_id, permission, expires_at
    )


async def revoke_group_acl(
    group_id: str,
    resource_type: str,
    resource_id: str,
    target_group_id: str,
    conn=None,
) -> None:
    """Revoke ACL permission from a group. (DEPRECATED)"""
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """DELETE FROM group_acl
           WHERE group_id = $1 AND resource_type = $2 AND resource_id = $3
           AND target_group_id = $4""",
        group_id, resource_type, resource_id, target_group_id
    )
