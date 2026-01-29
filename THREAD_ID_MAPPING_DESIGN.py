"""
Thread ID Flow: How We Map Users to Their Agents

This is the CRITICAL security boundary — if we mess this up,
User A could use User B's agent (with User B's MCP servers!).
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 1: THREAD ID EXTRACTION (Channel Layer)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from telegram import Update
from executive_assistant.storage.thread_storage import get_thread_id, set_thread_id


async def telegram_message_handler(update: Update, context):
    """
    Telegram channel: Extract thread_id from incoming message.
    """

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Extract unique chat ID from Telegram
    # ─────────────────────────────────────────────────────────────
    chat_id = update.effective_chat.id  # e.g., 6282871705

    # ─────────────────────────────────────────────────────────────
    # STEP 2: Add channel prefix (format: "channel:chat_id")
    # ─────────────────────────────────────────────────────────────
    thread_id = f"telegram:{chat_id}"  # e.g., "telegram:6282871705"

    # ─────────────────────────────────────────────────────────────
    # STEP 3: Store in ContextVar (thread-local storage)
    # ─────────────────────────────────────────────────────────────
    set_thread_id(thread_id)

    # ─────────────────────────────────────────────────────────────
    # STEP 4: Any code in this call stack can now access it
    # ─────────────────────────────────────────────────────────────
    print(f"Processing message for thread: {thread_id}")

    # Pass to agent (which will use get_thread_id() internally)
    response = await agent.ainvoke({"messages": [update.message.text]})


# HTTP Channel Example (for comparison)
async def http_message_handler(user_id: str, conversation_id: str, message: str):
    """
    HTTP channel: thread_id comes from request params.
    """

    # For HTTP, conversation_id IS the thread_id
    thread_id = conversation_id  # e.g., "user123_conversationA"

    set_thread_id(thread_id)

    response = await agent.ainvoke({"messages": [message]})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 2: THREAD ID IN AGENT BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_or_build_agent(thread_id: str | None = None) -> Runnable:
    """
    Get or build agent for the current thread.

    CRITICAL: If thread_id is None, this is a BUG!
    """

    # ─────────────────────────────────────────────────────────────
    # SAFETY CHECK: thread_id MUST be set
    # ─────────────────────────────────────────────────────────────
    if thread_id is None:
        # Try to get from ContextVar
        thread_id = get_thread_id()

    if thread_id is None:
        raise RuntimeError(
            "BUG: thread_id is None! Cannot safely determine which user's agent to use. "
            "This could cause User A to use User B's agent (SECURITY ISSUE)!"
        )

    # ─────────────────────────────────────────────────────────────
    # USE thread_id AS CACHE KEY
    # ─────────────────────────────────────────────────────────────
    if thread_id in _agent_cache:
        print(f"✅ Cache hit for thread: {thread_id}")
        return _agent_cache[thread_id].agent

    print(f"🔨 Building new agent for thread: {thread_id}")

    # Build agent for this specific thread
    agent = await _build_agent(thread_id)

    # Cache with thread_id as key
    _agent_cache[thread_id] = AgentCacheEntry(...)
    return agent


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 3: THREAD ID IN TOOLS (Storage Isolation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━────────────────────────────────

from executive_assistant.storage.file_sandbox import get_thread_id

@tool
def create_tdb_table(table_name: str, data: list) -> str:
    """
    Create a TDB table for the CURRENT user.

    How does it know which user? get_thread_id()!
    """

    # ─────────────────────────────────────────────────────────────
    # GET CURRENT THREAD ID (from ContextVar set by channel)
    # ─────────────────────────────────────────────────────────────
    thread_id = get_thread_id()

    if thread_id is None:
        return "Error: No thread context"

    # ─────────────────────────────────────────────────────────────
    # USE thread_id TO BUILD USER-SPECIFIC PATH
    # ─────────────────────────────────────────────────────────────
    user_db_path = Path(f"data/users/{thread_id}/tdb/{table_name}.db")

    # Create table in USER'S private directory
    # User A (telegram:111111) → data/users/telegram:111111/tdb/...
    # User B (telegram:222222) → data/users/telegram:222222/tdb/...
    ...


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 4: VISUAL FLOW DIAGRAM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
Telegram Message Flow:

┌─────────────────────────────────────────────────────────────┐
│ 1. Message arrives from Telegram                            │
│    chat_id = 6282871705                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Channel extracts thread_id                               │
│    thread_id = "telegram:6282871705"                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Store in ContextVar (thread-local)                       │
│    set_thread_id("telegram:6282871705")                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Call agent                                              │
│    agent.ainvoke({"messages": ["hello"]})                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Agent calls get_or_build_agent()                         │
│    Inside: get_thread_id() → "telegram:6282871705"         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Check cache: _agent_cache["telegram:6282871705"]        │
│    Found? → Return cached agent                            │
│    Not found? → Build new agent, cache it                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Process message with THIS USER's agent                  │
│    (Contains THIS USER's MCP servers)                       │
└─────────────────────────────────────────────────────────────┘
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 5: SECURITY CHECKLIST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def security_audit():
    """
    Checklist to ensure thread_id is used correctly everywhere.
    """

    checks = {
        "✅ Channel extracts thread_id correctly": [
            "Telegram: telegram:{chat_id}",
            "HTTP: {conversation_id}",
            "No channel should use constant value!",
        ],

        "✅ ContextVar is set before agent invocation": [
            "set_thread_id() called in message handler",
            "Not called inside agent (too late!)",
        ],

        "✅ Cache uses thread_id as key": [
            "_agent_cache[thread_id] = agent",
            "NOT: _agent_cache['default'] = agent (BUG!)",
        ],

        "✅ All tools use get_thread_id()": [
            "create_tdb_table → get_thread_id()",
            "write_file → get_thread_id()",
            "MCP tools → get_thread_id()",
        ],

        "✅ No global state pollution": [
            "Don't use global variables for user data",
            "Always use thread_id for isolation",
        ],

        "⚠️  Async safety": [
            "ContextVars are async-safe",
            "Thread A won't see Thread B's thread_id",
        ],
    }

    return checks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 6: REAL EXAMPLE WITH ACTUAL CODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Current implementation in executive_assistant:
# src/executive_assistant/channels/telegram.py

async def _process_message(self, update: Update, _) -> None:
    """Process a message from Telegram."""

    # ─────────────────────────────────────────────────────────────
    # Extract thread_id from Telegram chat
    # ─────────────────────────────────────────────────────────────
    chat_id = update.effective_chat.id
    thread_id = f"telegram:{chat_id}"

    # ─────────────────────────────────────────────────────────────
    # Set thread context (CRITICAL for storage isolation)
    # ─────────────────────────────────────────────────────────────
    set_thread_id(thread_id)
    set_channel("telegram")
    set_chat_type(update.effective_chat.type)

    # ─────────────────────────────────────────────────────────────
    # Get or build agent for THIS thread
    # ─────────────────────────────────────────────────────────────
    # Note: Currently uses global agent, but with per-thread cache:
    agent = await get_or_build_agent(thread_id)

    # ─────────────────────────────────────────────────────────────
    # Process message (tools will use get_thread_id() internally)
    # ─────────────────────────────────────────────────────────────
    async for event in agent.astream(...):
        # Handle events
        ...


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 7: COMMON BUGS TO AVOID
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def common_bugs():
    """
    These are WRONG ways to handle thread_id.
    """

    # ❌ BUG #1: Hardcoded thread_id
    # This makes ALL users share the same agent!
    def wrong_1():
        thread_id = "telegram:123456"  # WRONG!
        agent = get_or_build_agent(thread_id)

    # ❌ BUG #2: Not setting thread_id before agent call
    # This will cause get_thread_id() to return None
    def wrong_2():
        # Forgot to call set_thread_id()
        agent = get_or_build_agent()  # thread_id = None → CRASH!

    # ❌ BUG #3: Using global agent for all users
    # This bypasses the cache entirely
    def wrong_3():
        global_agent = create_agent()  # Created once at startup
        # All users use global_agent → User A's MCP visible to User B!

    # ❌ BUG #4: Caching by user_id instead of thread_id
    # This breaks multi-conversation support
    def wrong_4():
        # Telegram: user_id is same across all chats
        # Should use chat_id, not user_id!
        thread_id = f"telegram:{update.effective_user.id}"  # WRONG!


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 8: TESTING STRATEGY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_thread_isolation():
    """
    Verify that User A and User B get different agents.
    """

    # Simulate User A
    set_thread_id("telegram:111111")
    agent_a = await get_or_build_agent()
    print(f"User A agent: {id(agent_a)}")

    # Simulate User B
    set_thread_id("telegram:222222")
    agent_b = await get_or_build_agent()
    print(f"User B agent: {id(agent_b)}")

    # Verify they're different
    assert id(agent_a) != id(agent_b), "SECURITY BUG: Users share same agent!"

    # Verify cache entries
    assert "telegram:111111" in _agent_cache
    assert "telegram:222222" in _agent_cache

    print("✅ Thread isolation verified!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 9: SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
THREAD ID MAPPING SUMMARY:

1. Where does thread_id come from?
   - Telegram: chat_id from Update object
   - HTTP: conversation_id from request params
   - Format: "channel:id" (e.g., "telegram:6282871705")

2. How is it stored?
   - ContextVar (thread-local storage)
   - Set by channel before agent invocation
   - Retrieved by tools via get_thread_id()

3. How does the cache work?
   - Key: thread_id (e.g., "telegram:6282871705")
   - Value: Agent instance for that specific user
   - Lookup: _agent_cache[thread_id]

4. Security guarantee:
   - User A (telegram:111111) → cache["telegram:111111"]
   - User B (telegram:222222) → cache["telegram:222222"]
   - Completely isolated! ✅

5. What could go wrong?
   - Hardcoded thread_id → all users share agent ❌
   - Missing set_thread_id() → thread_id = None → crash ❌
   - Wrong ID source (user_id vs chat_id) → collisions ❌
"""
