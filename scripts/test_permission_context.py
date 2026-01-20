#!/usr/bin/env python3
"""
Test script to verify permission context is set correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cassey.storage.file_sandbox import set_thread_id, set_user_id
from cassey.storage.group_storage import (
    set_group_id,
    set_user_id as set_workspace_user_id,
    get_user_id as get_workspace_user_id,
    get_group_id,
)
from cassey.storage.helpers import sanitize_thread_id_to_user_id


async def test_permission_context():
    """Test that permission context is properly set for anonymous users."""
    print("\n" + "="*70)
    print("TEST: Permission Context for Anonymous Users")
    print("="*70)

    # Simulate what happens when a Telegram message comes in
    thread_id = "telegram:6282871705"  # Example thread_id
    identity_id = sanitize_thread_id_to_user_id(thread_id)

    print(f"\n📝 Simulating incoming message:")
    print(f"   thread_id: {thread_id}")
    print(f"   identity_id: {identity_id}")

    # Set context like base.py does
    set_thread_id(thread_id)
    print(f"   ✅ Set thread_id context: {thread_id}")

    # Simulate group setup
    group_id = f"group_{thread_id}"
    set_group_id(group_id)
    print(f"   ✅ Set group_id context: {group_id}")

    # Set user_id in group context (like base.py does)
    set_workspace_user_id(identity_id)
    print(f"   ✅ Set user_id context (workspace): {identity_id}")

    # Verify it was set
    verified_user_id = get_workspace_user_id()
    verified_group_id = get_group_id()

    print(f"\n📋 Verification:")
    print(f"   user_id from context: {verified_user_id}")
    print(f"   group_id from context: {verified_group_id}")

    # Test permission check
    from cassey.storage.group_storage import _check_permission_sync

    try:
        print(f"\n🔒 Testing permission check (read, group scope)...")
        _check_permission_sync("read", "group")
        print(f"   ✅ Permission check PASSED")
    except ValueError as e:
        print(f"   ❌ Permission check FAILED: {e}")
        return False

    # Test file sandbox context
    set_user_id(identity_id)
    print(f"\n📁 Testing file sandbox context...")
    from cassey.storage.file_sandbox import get_user_id as get_sandbox_user_id
    sandbox_user_id = get_sandbox_user_id()
    print(f"   user_id from sandbox context: {sandbox_user_id}")

    if sandbox_user_id == identity_id:
        print(f"   ✅ File sandbox context correct")
    else:
        print(f"   ❌ File sandbox context mismatch (expected {identity_id}, got {sandbox_user_id})")
        return False

    print(f"\n✅ ALL TESTS PASSED")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_permission_context())
    sys.exit(0 if result else 1)
