"""Tests for group storage and access control."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cassey.storage.group_storage import (
    # Context management
    set_group_id,
    get_group_id,
    clear_group_id,
    set_user_id,
    get_user_id,
    clear_user_id,
    # ID generation and sanitization
    generate_group_id,
    generate_anon_user_id,
    sanitize_thread_id,
    # Path resolution
    get_groups_root,
    get_group_path,
    get_group_files_path,
    get_group_kb_path,
    get_group_db_path,
    get_group_mem_path,
    # Access control
    can_access,
    ROLE_PERMISSIONS,
)


# =============================================================================
# Context Management Tests
# =============================================================================

class TestGroupContext:
    """Test group_id context variable management."""

    def test_set_and_get_group_id(self):
        """Test setting and getting group_id from context."""
        clear_group_id()
        assert get_group_id() is None

        set_group_id("test_group")
        assert get_group_id() == "test_group"

        clear_group_id()

    def test_context_isolation(self):
        """Test that context variable persists until cleared."""
        clear_group_id()
        set_group_id("group_1")
        assert get_group_id() == "group_1"

        # New value overrides
        set_group_id("group_2")
        assert get_group_id() == "group_2"

        clear_group_id()


class TestUserIdContext:
    """Test user_id context variable management."""

    def test_set_and_get_user_id(self):
        """Test setting and getting user_id from context."""
        clear_user_id()
        assert get_user_id() is None

        set_user_id("test_user")
        assert get_user_id() == "test_user"

        clear_user_id()


# =============================================================================
# ID Generation Tests
# =============================================================================

class TestIdGeneration:
    """Test ID generation functions."""

    def test_generate_group_id(self):
        """Test group ID generation."""
        group_id = generate_group_id()
        assert group_id.startswith("group:")
        assert len(group_id) > 10  # Has UUID after prefix

    def test_generate_anon_user_id(self):
        """Test anonymous user ID generation."""
        user_id = generate_anon_user_id()
        assert user_id.startswith("anon:")
        assert len(user_id) > 10

    def test_ids_are_unique(self):
        """Test that generated IDs are unique."""
        ids = [generate_group_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestSanitizeThreadId:
    """Test thread_id sanitization for filenames."""

    def test_sanitize_colons(self):
        """Test that colons are replaced."""
        assert sanitize_thread_id("telegram:user123") == "telegram_user123"

    def test_sanitize_slashes(self):
        """Test that slashes are replaced."""
        assert sanitize_thread_id("user/with/slash") == "user_with_slash"

    def test_sanitize_at_sign(self):
        """Test that @ signs are replaced."""
        assert sanitize_thread_id("email:user@example.com") == "email_user_example.com"

    def test_sanitize_backslashes(self):
        """Test that backslashes are replaced."""
        assert sanitize_thread_id(r"user\with\backslash") == "user_with_backslash"

    def test_sanitize_combined(self):
        """Test multiple special characters."""
        result = sanitize_thread_id("http:user:example@test/path\\slash")
        assert result == "http_user_example_test_path_slash"

    def test_sanitize_normal_text(self):
        """Test that normal text is unchanged."""
        assert sanitize_thread_id("normal_user_123") == "normal_user_123"


# =============================================================================
# Path Resolution Tests (with mocked settings)
# =============================================================================

class TestPathResolution:
    """Test group path resolution functions."""

    def test_get_groups_root(self, temp_groups_root):
        """Test getting groups root directory."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            root = get_groups_root()
            assert root == temp_groups_root

    def test_get_group_path(self, temp_groups_root):
        """Test getting path for a specific group."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            group_path = get_group_path("test_group")
            expected = temp_groups_root / "test_group"
            assert group_path == expected
            assert group_path.exists()

    def test_get_group_path_sanitizes(self, temp_groups_root):
        """Test that group path sanitizes special characters."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            group_path = get_group_path("group:with:special/chars")
            expected = temp_groups_root / "group_with_special_chars"
            assert group_path == expected

    def test_get_group_files_path(self, temp_groups_root):
        """Test getting files directory for a group."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            files_path = get_group_files_path("test_group")
            expected = temp_groups_root / "test_group" / "files"
            assert files_path == expected

    def test_get_group_kb_path(self, temp_groups_root):
        """Test getting KB directory for a group."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            kb_path = get_group_kb_path("test_group")
            expected = temp_groups_root / "test_group" / "kb"
            assert kb_path == expected

    def test_get_group_db_path(self, temp_groups_root):
        """Test getting DB file path for a group."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            db_path = get_group_db_path("test_group")
            expected = temp_groups_root / "test_group" / "db" / "db.db"
            assert db_path == expected
            assert db_path.parent.exists()

    def test_get_group_mem_path(self, temp_groups_root):
        """Test getting memory file path for a group."""
        with patch("cassey.storage.group_storage.settings.GROUPS_ROOT", temp_groups_root):
            mem_path = get_group_mem_path("test_group")
            expected = temp_groups_root / "test_group" / "mem" / "mem.db"
            assert mem_path == expected
            assert mem_path.parent.exists()


# =============================================================================
# Role Permissions Tests
# =============================================================================

class TestRolePermissions:
    """Test ROLE_PERMISSIONS configuration."""

    def test_admin_has_all_permissions(self):
        """Test admin role has all permissions."""
        perms = ROLE_PERMISSIONS["admin"]
        assert perms["read"] is True
        assert perms["write"] is True
        assert perms["admin"] is True

    def test_editor_has_read_write(self):
        """Test editor role has read and write but not admin."""
        perms = ROLE_PERMISSIONS["editor"]
        assert perms["read"] is True
        assert perms["write"] is True
        assert perms["admin"] is False

    def test_reader_has_only_read(self):
        """Test reader role has only read permission."""
        perms = ROLE_PERMISSIONS["reader"]
        assert perms["read"] is True
        assert perms["write"] is False
        assert perms["admin"] is False


# =============================================================================
# Access Control Tests (with mocked DB)
# =============================================================================

class TestAccessControl:
    """Test access control functions."""

    @pytest.fixture
    def mock_conn(self):
        """Create a mock database connection."""
        conn = AsyncMock()
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock()
        conn.fetch = AsyncMock()
        conn.fetchval = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_can_access_group_owner(self, mock_conn):
        """Test that group owner has full access."""
        # Mock: user is the group owner
        mock_conn.fetchval.return_value = "test_user"  # resolve_user_id returns same
        mock_conn.fetchrow.return_value = {
            "group_id": "test_group",
            "type": "individual",
            "name": "My Group",
            "owner_user_id": "test_user",  # User is owner
            "owner_group_id": None,
            "owner_system_id": None,
            "created_at": None,
        }

        with patch("cassey.storage.group_storage.get_db_conn", return_value=mock_conn):
            result = await can_access("test_user", "test_group", "read")
            assert result is True

            result = await can_access("test_user", "test_group", "write")
            assert result is True

            result = await can_access("test_user", "test_group", "admin")
            assert result is True

    @pytest.mark.asyncio
    async def test_can_access_public_group_read(self, mock_conn):
        """Test that everyone can read public groups."""
        mock_conn.fetchval.return_value = "test_user"
        mock_conn.fetchrow.side_effect = [
            {
                "group_id": "test_group",
                "type": "public",  # Public group
                "name": "Public Group",
                "owner_user_id": None,
                "owner_group_id": None,
                "owner_system_id": None,
                "created_at": None,
            },
            None,  # No membership
            None,  # No team membership
            None,  # No ACL
        ]

        with patch("cassey.storage.group_storage.get_db_conn", return_value=mock_conn):
            result = await can_access("test_user", "test_group", "read")
            assert result is True

            result = await can_access("test_user", "test_group", "write")
            assert result is False

    @pytest.mark.asyncio
    async def test_can_access_denied(self, mock_conn):
        """Test access denied when no permissions exist."""
        mock_conn.fetchval.return_value = "test_user"
        mock_conn.fetchrow.side_effect = [
            {
                "group_id": "test_group",
                "type": "private",  # Private group
                "name": "Private Group",
                "owner_user_id": None,
                "owner_group_id": None,
                "owner_system_id": None,
                "created_at": None,
            },
            None,  # No membership
            None,  # No team membership
            None,  # No ACL
        ]

        with patch("cassey.storage.group_storage.get_db_conn", return_value=mock_conn):
            result = await can_access("test_user", "test_group", "read")
            assert result is False

            result = await can_access("test_user", "test_group", "write")
            assert result is False


# =============================================================================
# Integration Tests with Real PostgreSQL
# =============================================================================

@pytest.mark.postgres
class TestGroupStoragePostgreSQL:
    """Integration tests with real PostgreSQL database."""

    @pytest.mark.asyncio
    async def test_ensure_user_creates_user(self, db_conn, clean_test_data):
        """Test that ensure_user creates a user record."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import ensure_user

        group_id = await ensure_user(user_id, db_conn)

        # Verify user was created
        exists = await db_conn.fetchval(
            "SELECT 1 FROM users WHERE user_id = $1",
            user_id
        )
        assert exists == 1

    @pytest.mark.asyncio
    async def test_ensure_user_group_creates_group(self, db_conn, clean_test_data):
        """Test that ensure_user_group creates individual group."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import ensure_user_group

        group_id = await ensure_user_group(user_id, db_conn)

        # Verify group was created
        group_info = await db_conn.fetchrow(
            "SELECT group_id, type, owner_user_id FROM groups WHERE group_id = $1",
            group_id
        )
        assert group_info is not None
        assert group_info["type"] == "individual"
        assert group_info["owner_user_id"] == user_id

        # Verify user_workspaces mapping
        mapped = await db_conn.fetchval(
            "SELECT group_id FROM user_workspaces WHERE user_id = $1",
            user_id
        )
        assert mapped == group_id

    @pytest.mark.asyncio
    async def test_ensure_user_group_idempotent(self, db_conn, clean_test_data):
        """Test that ensure_user_group returns same group on second call."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import ensure_user_group

        group_id_1 = await ensure_user_group(user_id, db_conn)
        group_id_2 = await ensure_user_group(user_id, db_conn)

        assert group_id_1 == group_id_2

        # Verify only one group was created
        count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM user_workspaces WHERE user_id = $1",
            user_id
        )
        assert count == 1

    @pytest.mark.asyncio
    async def test_ensure_thread_group(self, db_conn, clean_test_data):
        """Test that ensure_thread_group creates group and maps thread."""
        thread_id = f"test_thread_{uuid.uuid4().hex[:8]}"
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import ensure_thread_group

        group_id = await ensure_thread_group(thread_id, user_id, db_conn)

        # Verify thread_groups mapping
        mapped = await db_conn.fetchval(
            "SELECT group_id FROM thread_groups WHERE thread_id = $1",
            thread_id
        )
        assert mapped == group_id

        # Verify user has individual group
        user_group = await db_conn.fetchval(
            "SELECT group_id FROM user_workspaces WHERE user_id = $1",
            user_id
        )
        assert user_group == group_id

    @pytest.mark.asyncio
    async def test_resolve_user_id_with_alias(self, db_conn, clean_test_data):
        """Test user ID resolution with aliases."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        alias_id = f"alias_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import ensure_user, add_alias, resolve_user_id

        # Create user and alias
        await ensure_user(user_id, db_conn)
        await db_conn.execute(
            "INSERT INTO user_aliases (user_id, alias_id) VALUES ($1, $2)",
            user_id, alias_id
        )

        # Resolve alias to canonical user_id
        resolved = await resolve_user_id(alias_id, db_conn)
        assert resolved == user_id

        # Non-alias returns itself
        resolved = await resolve_user_id(user_id, db_conn)
        assert resolved == user_id

    @pytest.mark.asyncio
    async def test_accessible_groups(self, db_conn, clean_test_data):
        """Test getting accessible groups for a user."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import (
            ensure_user_group, accessible_groups
        )

        # Create individual group
        group_id = await ensure_user_group(user_id, db_conn)

        # Get accessible groups
        groups = await accessible_groups(user_id, db_conn)

        assert len(groups) >= 1
        assert any(g["group_id"] == group_id for g in groups)
        assert any(g["role"] == "admin" for g in groups)

    @pytest.mark.asyncio
    async def test_get_group_info(self, db_conn, clean_test_data):
        """Test getting group information."""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        from cassey.storage.group_storage import ensure_user_group, get_group_info

        group_id = await ensure_user_group(user_id, db_conn)
        info = await get_group_info(group_id, db_conn)

        assert info is not None
        assert info["group_id"] == group_id
        assert info["type"] == "individual"
        assert info["owner_user_id"] == user_id
