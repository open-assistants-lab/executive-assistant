#!/usr/bin/env python3
"""
Test VDB tools with proper thread context set.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from executive_assistant.storage.thread_storage import set_thread_id
from executive_assistant.storage.vs_tools import vdb_list


async def test_vdb_list_tool():
    """Test that vdb_list works with proper context."""
    print("\n" + "="*70)
    print("TEST: VDB List Tool with Thread Context")
    print("="*70)

    # Simulate Telegram user context
    thread_id = "telegram:6282871705"
    print(f"\n📝 Setting context for Telegram user:")
    print(f"   thread_id: {thread_id}")

    # Set all contexts
    set_thread_id(thread_id)

    print(f"   ✅ Context set successfully")

    # Test vdb_list tool
    print(f"\n🔍 Testing vdb_list tool...")
    try:
        result = vdb_list.invoke({})
        print(f"   Result: {result}")

        print(f"   ✅ vdb_list executed successfully")
        return True
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_vdb_list_tool())
    sys.exit(0 if result else 1)
