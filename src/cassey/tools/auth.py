"""Access control wrappers for group/storage operations.

This module re-exports permission checking decorators from group_storage.
The decorators are implemented in group_storage to avoid circular imports.

Usage:
    from cassey.tools.auth import require_permission, require_group_context

    @require_permission("write")
    def my_tool(arg: str) -> str:
        return arg
"""

from cassey.storage.group_storage import (
    require_permission,
    require_group_context,
)

__all__ = ["require_permission", "require_group_context"]

# Backward compatibility alias
require_workspace_context = require_group_context
