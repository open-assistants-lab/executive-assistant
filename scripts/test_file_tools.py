#!/usr/bin/env python3
"""
Test file tools with proper context set.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from executive_assistant.storage.file_sandbox import (
    set_thread_id,
    set_user_id,
    list_files,
)
from executive_assistant.storage.group_storage import (
    set_group_id,
    set_user_id as set_workspace_user_id,
)
from executive_assistant.storage.helpers import sanitize_thread_id_to_user_id


async def test_file_list_tool():
    """Test that list_files works with proper context."""
    print("\n" + "="*70)
    print("TEST: File List Tool with Permission Context")
    print("="*70)

    # Simulate Telegram user context
    thread_id = "telegram:6282871705"
    identity_id = sanitize_thread_id_to_user_id(thread_id)

    print(f"\n📝 Setting context for Telegram user:")
    print(f"   thread_id: {thread_id}")
    print(f"   identity_id: {identity_id}")

    # Set all contexts
    set_thread_id(thread_id)
    group_id = f"group_{thread_id}"
    set_group_id(group_id)
    set_workspace_user_id(identity_id)
    set_user_id(identity_id)

    print(f"   ✅ Context set successfully")

    # Test list_files tool
    print(f"\n📁 Testing list_files tool...")
    try:
        result = list_files.invoke({"directory": "", "recursive": False, "scope": "context"})
        print(f"   Result: {result}")

        if "Error" in result and "permission check failed" in result.lower():
            print(f"   ❌ Permission check still failing!")
            return False
        else:
            print(f"   ✅ list_files executed successfully")
            return True
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_file_list_tool())
    sys.exit(0 if result else 1)
