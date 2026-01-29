"""
Per-Thread Agent Cache Design for User MCP Support

This shows how User A's MCP rebuild won't affect Users B, C, D.
"""

from pathlib import Path
from typing import Runnable
from langgraph.types import Runnable as LangGraphRunnable
from datetime import datetime
import time

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CACHE STRUCTURE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentCacheEntry:
    """Cached agent instance for a specific thread."""
    def __init__(
        self,
        agent: Runnable,
        mcp_mtime: float,  # Last modified time of MCP config
        last_used: float,  # Last access time
    ):
        self.agent = agent
        self.mcp_mtime = mcp_mtime
        self.last_used = last_used


# Global cache (max 100 entries)
_agent_cache: dict[str, AgentCacheEntry] = {}
_MAX_CACHE_SIZE = 100


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_or_build_agent(thread_id: str, base_agent_builder) -> Runnable:
    """
    Get cached agent or build new one for this thread.

    This is the key function that ensures isolation:
    - User A's rebuild doesn't affect User B's cache
    - Each thread has its own agent instance
    """

    # Check if user has MCP config
    mcp_path = Path(f"data/users/{thread_id}/mcp/local.json")
    current_mtime = mcp_path.stat().st_mtime if mcp_path.exists() else 0

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Check cache
    # ─────────────────────────────────────────────────────────────
    if thread_id in _agent_cache:
        entry = _agent_cache[thread_id]

        # Check if MCP config changed
        if entry.mcp_mtime == current_mtime:
            # Cache hit! No rebuild needed.
            entry.last_used = time.time()
            print(f"[{thread_id}] Cache HIT ✅ (no rebuild)")
            return entry.agent
        else:
            # MCP config changed → invalidate this entry only
            print(f"[{thread_id}] Cache INVALIDATED (MCP config changed)")
            del _agent_cache[thread_id]

    # ─────────────────────────────────────────────────────────────
    # STEP 2: Build agent for this thread
    # ─────────────────────────────────────────────────────────────
    print(f"[{thread_id}] Cache MISS → Building new agent...")

    # Load user's MCP config (if exists)
    user_mcp_tools = await _load_user_mcp_tools(thread_id)

    # Build agent (base + user MCP)
    agent = await _build_agent_for_thread(thread_id, user_mcp_tools, base_agent_builder)

    # Cache it
    _agent_cache[thread_id] = AgentCacheEntry(
        agent=agent,
        mcp_mtime=current_mtime,
        last_used=time.time(),
    )

    # Evict oldest if cache too big
    _evict_if_needed()

    print(f"[{thread_id}] New agent built & cached ✅")
    return agent


async def invalidate_cache(thread_id: str) -> None:
    """
    Manually invalidate cache for a specific thread.

    Called when user adds/removes MCP servers via /mcp commands.
    """
    if thread_id in _agent_cache:
        del _agent_cache[thread_id]
        print(f"[{thread_id}] Cache invalidated (manual)")


def _evict_if_needed() -> None:
    """Evict oldest cache entry if cache is full."""
    if len(_agent_cache) > _MAX_CACHE_SIZE:
        # Find least recently used entry
        oldest_thread = min(_agent_cache.keys(), key=lambda k: _agent_cache[k].last_used)
        del _agent_cache[oldest_thread]
        print(f"[{oldest_thread}] Evicted from cache (LRU)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP LOADING (simplified)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _load_user_mcp_tools(thread_id: str) -> list:
    """Load MCP tools for a specific thread."""
    mcp_path = Path(f"data/users/{thread_id}/mcp/local.json")

    if not mcp_path.exists():
        return []  # No user MCP

    # Load config, connect to servers, fetch tools
    # ... (MCP connection logic here)
    return [f"mcp_tool_1_for_{thread_id}", f"mcp_tool_2_for_{thread_id}"]


async def _build_agent_for_thread(thread_id: str, user_mcp_tools: list, base_builder) -> Runnable:
    """Build agent with base tools + user MCP tools."""
    # Get base agent (71 tools + admin MCP)
    base_agent = await base_builder()

    # Add user MCP tools
    # ... (merge tools here)

    return base_agent


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USAGE EXAMPLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_user_message(thread_id: str, message: str):
    """Handle a user message with per-thread agent caching."""

    # Get or build agent for THIS THREAD ONLY
    agent = await get_or_build_agent(thread_id, base_agent_builder=...)

    # Process message
    response = await agent.ainvoke({"messages": [message]})
    return response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO: User A adds MCP, User B unaffected
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def scenario_demo():
    """
    Demonstrates that User A's MCP add doesn't affect User B.
    """

    print("\n" + "="*70)
    print("SCENARIO: User A adds MCP server while User B is chatting")
    print("="*70 + "\n")

    # ─────────────────────────────────────────────────────────────
    # T=0: Both users start chatting
    # ─────────────────────────────────────────────────────────────

    print("T=0s: Both users send first message")
    print("─" * 70)

    agent_a = await get_or_build_agent("telegram:111111", base_agent_builder=...)
    # Output: [telegram:111111] Cache MISS → Building new agent...

    agent_b = await get_or_build_agent("telegram:222222", base_agent_builder=...)
    # Output: [telegram:222222] Cache MISS → Building new agent...

    print(f"Cache size: {len(_agent_cache)} (2 agents)\n")

    # ─────────────────────────────────────────────────────────────
    # T=10: User A adds MCP server
    # ─────────────────────────────────────────────────────────────

    print("T=10s: User A runs /mcp add filesystem")
    print("─" * 70)

    # Update MCP config
    mcp_path = Path("data/users/telegram:111111/mcp/local.json")
    mcp_path.parent.mkdir(parents=True, exist_ok=True)
    mcp_path.write_text('{"servers": {"filesystem": {...}}}')
    time.sleep(0.1)  # Ensure mtime changes

    # Invalidate cache for User A ONLY
    await invalidate_cache("telegram:111111")
    # Output: [telegram:111111] Cache invalidated (manual)

    print(f"Cache size: {len(_agent_cache)} (1 agent - User B still cached!)\n")

    # ─────────────────────────────────────────────────────────────
    # T=11: User B sends message (UNAFFECTED)
    # ─────────────────────────────────────────────────────────────

    print("T=11s: User B sends message")
    print("─" * 70)

    agent_b_2 = await get_or_build_agent("telegram:222222", base_agent_builder=...)
    # Output: [telegram:222222] Cache HIT ✅ (no rebuild)

    print("→ User B's message processed immediately ✅\n")

    # ─────────────────────────────────────────────────────────────
    # T=12: User A sends message (REBUILD)
    # ─────────────────────────────────────────────────────────────

    print("T=12s: User A sends first message after MCP add")
    print("─" * 70)

    agent_a_2 = await get_or_build_agent("telegram:111111", base_agent_builder=...)
    # Output: [telegram:111111] Cache MISS → Building new agent...
    #         [telegram:111111] New agent built & cached ✅

    print("→ User A's message processed after rebuild (5-10s)\n")

    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────

    print("="*70)
    print("RESULT:")
    print("="*70)
    print("✅ User B was NEVER affected by User A's MCP change")
    print("✅ User B's agent stayed in cache the whole time")
    print("✅ Only User A's agent was rebuilt")
    print("✅ Zero cross-user impact")
    print("="*70 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(scenario_demo())
