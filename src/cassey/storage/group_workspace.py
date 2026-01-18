"""Team group management functions.

This module provides functions for creating and managing team groups,
which allow multiple users to collaborate with role-based access.

Note: This creates "team groups" (collections of users), not "storage groups"
(formerly workspaces). Team groups can own storage groups for collaboration.
"""

import uuid
from typing import Literal

from cassey.storage.group_storage import (
    generate_group_id,
    get_db_conn,
)


def generate_team_group_id() -> str:
    """Generate a new unique team group ID (format: team:{uuid})."""
    return f"team:{uuid.uuid4()}"


async def create_team_group(
    name: str,
    conn=None,
) -> str:
    """
    Create a new team group.

    Args:
        name: Display name for the team group
        conn: Optional database connection

    Returns:
        The new team_group_id (format: team:{uuid})
    """
    if conn is None:
        conn = await get_db_conn()

    team_group_id = generate_team_group_id()

    await conn.execute(
        "INSERT INTO team_groups (group_id, name) VALUES ($1, $2)",
        team_group_id, name
    )

    return team_group_id


# Backward compatibility alias
create_group = create_team_group


async def create_group_workspace(
    team_group_id: str,
    name: str,
    conn=None,
) -> str:
    """
    Create a storage group owned by a team group.

    Args:
        team_group_id: The team group ID that will own this storage group
        name: Display name for the storage group
        conn: Optional database connection

    Returns:
        The new group_id (format: group:{uuid})
    """
    if conn is None:
        conn = await get_db_conn()

    group_id = generate_group_id()

    async with conn.transaction():
        # Create storage group (formerly workspace)
        await conn.execute(
            """INSERT INTO groups (group_id, type, name, owner_group_id)
               VALUES ($1, 'group', $2, $3)""",
            group_id, name, team_group_id
        )

        # Map team_group to storage group (using storage_group_id column)
        await conn.execute(
            "INSERT INTO group_workspaces (group_id, storage_group_id) VALUES ($1, $2)",
            team_group_id, group_id
        )

    return group_id


async def add_team_group_member(
    team_group_id: str,
    user_id: str,
    role: Literal["admin", "member"] = "member",
    conn=None,
) -> None:
    """
    Add a user to a team group with a role.

    Args:
        team_group_id: The team group ID
        user_id: The user ID to add
        role: Either 'admin' or 'member'
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        """INSERT INTO team_group_members (group_id, user_id, role)
           VALUES ($1, $2, $3)
           ON CONFLICT (group_id, user_id) DO UPDATE SET role = $3""",
        team_group_id, user_id, role
    )


# Backward compatibility alias
add_group_member = add_team_group_member


async def remove_team_group_member(
    team_group_id: str,
    user_id: str,
    conn=None,
) -> None:
    """
    Remove a user from a team group.

    Args:
        team_group_id: The team group ID
        user_id: The user ID to remove
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        "DELETE FROM team_group_members WHERE group_id = $1 AND user_id = $2",
        team_group_id, user_id
    )


# Backward compatibility alias
remove_group_member = remove_team_group_member


async def get_team_group_members(
    team_group_id: str,
    conn=None,
) -> list[dict]:
    """
    Get all members of a team group.

    Args:
        team_group_id: The team group ID
        conn: Optional database connection

    Returns:
        List of member dicts with user_id, role, joined_at
    """
    if conn is None:
        conn = await get_db_conn()

    rows = await conn.fetch(
        """SELECT user_id, role, joined_at
           FROM team_group_members
           WHERE group_id = $1
           ORDER BY joined_at""",
        team_group_id
    )

    return [
        {
            "user_id": row["user_id"],
            "role": row["role"],
            "joined_at": row["joined_at"],
        }
        for row in rows
    ]


# Backward compatibility alias
get_group_members = get_team_group_members


async def get_team_group_info(
    team_group_id: str,
    conn=None,
) -> dict | None:
    """
    Get team group information.

    Args:
        team_group_id: The team group ID
        conn: Optional database connection

    Returns:
        Team group info dict or None if not found
    """
    if conn is None:
        conn = await get_db_conn()

    row = await conn.fetchrow(
        "SELECT group_id, name, created_at FROM team_groups WHERE group_id = $1",
        team_group_id
    )

    if not row:
        return None

    return {
        "group_id": row["group_id"],
        "name": row["name"],
        "created_at": row["created_at"],
    }


# Backward compatibility alias
get_group_info = get_team_group_info


async def list_team_groups(
    conn=None,
) -> list[dict]:
    """
    List all team groups.

    Args:
        conn: Optional database connection

    Returns:
        List of team group dicts
    """
    if conn is None:
        conn = await get_db_conn()

    rows = await conn.fetch(
        "SELECT group_id, name, created_at FROM team_groups ORDER BY name"
    )

    return [
        {
            "group_id": row["group_id"],
            "name": row["name"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# Backward compatibility alias
list_groups = list_team_groups


async def delete_team_group(
    team_group_id: str,
    conn=None,
) -> None:
    """
    Delete a team group and all its storage groups.

    WARNING: This will cascade delete all storage groups owned by
    this team group and their associated data.

    Args:
        team_group_id: The team group ID to delete
        conn: Optional database connection
    """
    if conn is None:
        conn = await get_db_conn()

    await conn.execute(
        "DELETE FROM team_groups WHERE group_id = $1",
        team_group_id
    )


# Backward compatibility alias
delete_group = delete_team_group
