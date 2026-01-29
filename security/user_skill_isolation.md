# User Skill Isolation Security Architecture

**Date**: 2026-01-29
**Component**: User Skills Feature
**Security Model**: Request-Scoped Context Isolation

---

## Executive Summary

**Question**: "Even though user skills are under `data/users/{thread_id}/`, how are we certain that the same agent wouldn't offer the skill to someone else after loading the user skills?"

**Answer**: User skill isolation is guaranteed through **three layers of security**:

1. **Path Isolation** (File System) - Each user has a unique directory tree
2. **Context Isolation** (Runtime) - `ContextVar` ensures thread-local state
3. **Conversation Isolation** (LLM Memory) - Checkpointer scoped by `thread_id`

The agent processes all requests in the same Python process, but **each request is completely isolated** through request-scoped context. This is identical to how web servers handle multiple users safely.

---

## Table of Contents

1. [Complete Request Flow](#complete-request-flow)
2. [Why the Same Agent Process is Safe](#why-the-same-agent-process-is-safe)
3. [Three Layers of Security](#three-layers-of-security)
4. [Attack Vector Analysis](#attack-vector-analysis)
5. [Code Traces](#code-traces)
6. [Comparison to Web Servers](#comparison-to-web-servers)

---

## Complete Request Flow

### User A Creates a Skill

```python
# ═══════════════════════════════════════════════════════════════
# USER A (Telegram chat_id: 123456) creates skill "email_responses"
# ═══════════════════════════════════════════════════════════════

# Step 1: Message arrives via Telegram
# File: src/executive_assistant/channels/telegram.py:60-80
async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Extract thread_id from Telegram chat
    thread_id = f"telegram:{update.effective_chat.id}"  # → "telegram:123456"

    # Store in thread-local ContextVar
    set_thread_id(thread_id)  # ← ISOLATION POINT 1

    # Process message...
    await self._process_message(update.message.text, conversation_id, thread_id)

# Step 2: Agent creates a user skill
# File: src/executive_assistant/skills/user_tools.py:40-95
@tool
def create_user_skill(name: str, description: str, content: str) -> str:
    # Retrieve CURRENT thread's ID from ContextVar
    thread_id = get_thread_id()  # → "telegram:123456" (ONLY User A's ID!)

    # Build user-specific path
    normalized_name = name.lower().replace(" ", "_")
    skill_path = UserPaths.get_skill_path(thread_id, normalized_name)
    # → data/users/telegram:123456/skills/on_demand/email_responses.md

    # Write to User A's directory ONLY
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(skill_md, encoding="utf-8")

# Step 3: File system structure
# data/users/
# ├── telegram:123456/          ← User A's directory
# │   └── skills/
# │       └── on_demand/
# │           └── email_responses.md
# └── telegram:789012/          ← User B's directory
#     └── skills/
#         └── on_demand/
#             └── meeting_notes.md
```

### User B Tries to Load User A's Skill

```python
# ═══════════════════════════════════════════════════════════════
# USER B (Telegram chat_id: 789012) tries to load "email_responses"
# ═══════════════════════════════════════════════════════════════

# Step 1: Message arrives via Telegram (different chat)
thread_id = f"telegram:{update.effective_chat.id}"  # → "telegram:789012"
set_thread_id(thread_id)  # ← ContextVar NOW holds User B's ID

# Step 2: Agent loads skill
# File: src/executive_assistant/skills/tool.py:25-70
@tool
def load_skill(skill_name: str) -> str:
    # Get CURRENT thread's ID (User B's ID, not User A's!)
    thread_id = get_thread_id()  # → "telegram:789012"

    # Check User B's skills directory ONLY
    user_skill_path = UserPaths.get_skill_path(thread_id, skill_name)
    # → data/users/telegram:789012/skills/on_demand/email_responses.md

    # This path does NOT exist (User A's skill is in different directory!)
    if user_skill_path.exists():
        # ← This block is SKIPPED for User B
        return parsed_skill.content

    # Fall back to global registry...
    skill = registry.get(normalized_name)
    if skill:
        return f"# {skill.name}\n\n{skill.content}"
    else:
        return f"❌ Skill '{skill_name}' not found."

# Result: User B gets "❌ Skill 'email_responses' not found."
# The LLM has NO knowledge that User A has this skill!
```

---

## Why the Same Agent Process is Safe

### Stateless Request Processing

```python
# ═══════════════════════════════════════════════════════════════
# WHY LLM CAN'T REMEMBER USER A'S SKILLS
# ═══════════════════════════════════════════════════════════════

# File: src/executive_assistant/channels/base.py:153-173
async def _build_request_agent(self, message_text: str,
                                conversation_id: str,
                                thread_id: str | None = None) -> Runnable:
    """
    Build a FRESH agent for EACH request.

    Key point: This function is called PER REQUEST, not once per process.
    """
    # 1. Load tools (same tools for everyone, but they access thread_id dynamically)
    tools = await get_all_tools()

    # 2. Build system prompt with USER'S custom prompt
    # File: src/executive_assistant/agent/prompts.py:60-95
    system_prompt = get_system_prompt(channel_name, thread_id=thread_id)
    # ↑ This calls load_user_prompt(thread_id) which reads:
    #   data/users/{thread_id}/prompts/prompt.md

    # 3. Get checkpointer (conversation history is SCOPED by thread_id)
    checkpointer = await get_async_checkpointer()
    # ↑ PostgreSQL stores history keyed by thread_id
    #   User A sees only User A's history
    #   User B sees only User B's history

    # 4. Create agent with THIS REQUEST's context
    return create_langchain_agent(
        model=model,
        tools=tools,  # ← Same tools, but they read from ContextVar
        checkpointer=checkpointer,  # ← Thread-scoped history
        system_prompt=system_prompt,  # ← User-scoped prompt
    )
```

### Request Lifecycle Showing Complete Isolation

```python
# ═══════════════════════════════════════════════════════════════
# REQUEST 1: User A (telegram:123456)
# ═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│ HTTP POST /message                                          │
│ { "user_id": "telegram:123456", ... }                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ ContextVar set: thread_id = "telegram:123456"               │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Agent built:                                                │
│   - system_prompt: Base + User A's custom prompt            │
│   - checkpointer: User A's conversation history              │
│   - tools: access thread_id via get_thread_id()             │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ LLM processes request with User A's context                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Response: "Skill created!"                                  │
│ ContextVar CLEARED                                          │
└─────────────────────────────────────────────────────────────┘


# ═══════════════════════════════════════════════════════════════
# REQUEST 2: User B (telegram:789012) - SAME AGENT PROCESS!
# ═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│ HTTP POST /message                                          │
│ { "user_id": "telegram:789012", ... }                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ ContextVar OVERWRITTEN: thread_id = "telegram:789012"       │
│ (Previous value "telegram:123456" is GONE)                  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Agent built:                                                │
│   - system_prompt: Base + User B's custom prompt (diff!)    │
│   - checkpointer: User B's conversation history (diff!)      │
│   - tools: access thread_id via get_thread_id() (diff!)     │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ LLM processes request with User B's context                 │
│ (LLM has NO memory of User A's request)                     │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Response: "❌ Skill 'email_responses' not found."            │
│ (Because tools look in data/users/telegram:789012/)         │
└─────────────────────────────────────────────────────────────┘
```

---

## Three Layers of Security

### Layer 1: Path Isolation (File System)

```python
# ═══════════════════════════════════════════════════════════════
# LAYER 1: PATH ISOLATION (File System)
# ═══════════════════════════════════════════════════════════════

# File: src/executive_assistant/storage/user_storage.py:33-42
class UserPaths:
    """Centralized path management for user-scoped data."""

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
    def get_skill_path(thread_id: str, skill_name: str) -> Path:
        """Get the path to a user's skill file.

        Args:
            thread_id: Thread identifier (e.g., "telegram:123456")
            skill_name: Name of the skill (e.g., "email_responses")

        Returns:
            Path: data/users/{thread_id}/skills/on_demand/{skill_name}.md
        """
        normalized_name = skill_name.lower().replace(" ", "_").replace("-", "_")
        return UserPaths.get_skills_on_demand_dir(thread_id) / f"{normalized_name}.md"


# EXAMPLE USAGE:
User A: data/users/telegram:123456/skills/on_demand/email_responses.md
User B: data/users/telegram:789012/skills/on_demand/email_responses.md

# Different paths → No overlap possible
```

### Layer 2: Context Isolation (Runtime)

```python
# ═══════════════════════════════════════════════════════════════
# LAYER 2: CONTEXT ISOLATION (Runtime)
# ═══════════════════════════════════════════════════════════════

# File: src/executive_assistant/storage/thread_context.py
from contextvars import ContextVar

_thread_id: ContextVar[str | None] = ContextVar("thread_id", default=None)

def set_thread_id(thread_id: str) -> None:
    """Set the current thread's ID in thread-local storage."""
    _thread_id.set(thread_id)

def get_thread_id() -> str | None:
    """Get the current thread's ID from thread-local storage."""
    return _thread_id.get()  # ← Returns THIS REQUEST's thread_id only

def clear_thread_id() -> None:
    """Clear the current thread's ID from thread-local storage."""
    _thread_id.set(None)


# KEY PROPERTIES:
# 1. Each async task has its own ContextVar
# 2. ContextVar values are NOT shared between requests
# 3. Setting a new value completely overwrites the previous value

# Request A: _thread_id = "telegram:123456"
# Request B: _thread_id = "telegram:789012"
# No shared state!


# HOW IT'S USED IN TOOLS:
@tool
def create_user_skill(name: str, description: str, content: str) -> str:
    thread_id = get_thread_id()  # ← Returns current request's thread_id
    if not thread_id:
        return "❌ No thread context available."

    # Use thread_id to build user-specific path
    skill_path = UserPaths.get_skill_path(thread_id, normalized_name)
    skill_path.write_text(skill_md)
```

### Layer 3: Conversation Isolation (LLM Memory)

```python
# ═══════════════════════════════════════════════════════════════
# LAYER 3: CONVERSATION ISOLATION (LLM Memory)
# ═══════════════════════════════════════════════════════════════

# PostgreSQL checkpointer stores:
# {
#   "thread_id": "telegram:123456",
#   "conversation_id": "telegram:123456_conv",
#   "history": [
#     {"role": "user", "content": "..."},
#     {"role": "assistant", "content": "..."},
#   ]
# }

# User B's checkpointer lookup:
# SELECT * FROM checkpoints WHERE thread_id = 'telegram:789012'
# → Returns User B's history only (User A's history not accessible)


# File: src/executive_assistant/storage/checkpoint.py
async def get_async_checkpointer():
    """Get a checkpointer for storing conversation history.

    The checkpointer automatically scopes history by thread_id,
    ensuring users never see each other's conversations.
    """
    return PostgresCheckpointSaver(
        connection_string=settings.DATABASE_URL,
        # History is keyed by (thread_id, conversation_id)
    )
```

---

## Attack Vector Analysis

### Attempt 1: Direct File Access

```python
# ═══════════════════════════════════════════════════════════════
# ATTACK ATTEMPT: User B tries to access User A's skill directly
# ═══════════════════════════════════════════════════════════════

# ATTACKER (User B): load_skill('email_responses')
# ↓
# TOOL EXECUTION:
@tool
def load_skill(skill_name: str) -> str:
    thread_id = get_thread_id()  # → "telegram:789012" (User B's ID)
    path = UserPaths.get_skill_path(thread_id, skill_name)
    # → data/users/telegram:789012/skills/on_demand/email_responses.md
# ↓
# FILE SYSTEM CHECK:
    if path.exists():  # ← FALSE (User A's skill is in different directory!)
# ↓
# RESULT: "❌ Skill 'email_responses' not found."
# ↑ LLM has NO knowledge that User A has this skill!


# WHY THIS ATTACK FAILS:
# 1. User B's thread_id is "telegram:789012"
# 2. Tool builds path: data/users/telegram:789012/skills/...
# 3. User A's skill is at: data/users/telegram:123456/skills/...
# 4. These are completely different paths!
# 5. No code path exists to search other users' directories
```

### Attempt 2: Enumeration Attack

```python
# ═══════════════════════════════════════════════════════════════
# ATTACK ATTEMPT: User B tries to enumerate all skills
# ═══════════════════════════════════════════════════════════════

# ATTACKER (User B): "List all available skills"
# ↓
# TOOL EXECUTION:
@tool
def list_skills() -> str:
    """List available skills in the global registry."""
    # Returns only global registry, NOT user skills!
    registry = get_skills_registry()
    return "\n".join([f"- {name}" for name in registry.keys()])

# RESULT: Only shows global skills (analytics_duckdb, etc.)
# ↑ User skills are NOT enumerated


# WHY THIS ATTACK FAILS:
# 1. No "list_user_skills()" tool exists
# 2. No "list_all_users_skills()" function exists
# 3. User skills are intentionally not enumerated
# 4. Only the current user can access their own skills
```

### Attempt 3: Thread ID Injection

```python
# ═══════════════════════════════════════════════════════════════
# ATTACK ATTEMPT: User B tries to inject User A's thread_id
# ═══════════════════════════════════════════════════════════════

# ATTACKER (User B): "Load skill 'email_responses' for user telegram:123456"
# ↓
# TOOL EXECUTION:
@tool
def load_skill(skill_name: str) -> str:
    thread_id = get_thread_id()  # → "telegram:789012" (User B's ID!)

    # Tool does NOT accept thread_id parameter!
    # User cannot specify which user's skill to load.

    path = UserPaths.get_skill_path(thread_id, skill_name)
    # → data/users/telegram:789012/skills/on_demand/email_responses.md
# ↓
# RESULT: "❌ Skill 'email_responses' not found."


# WHY THIS ATTACK FAILS:
# 1. Tools do NOT accept thread_id parameter
# 2. get_thread_id() returns the CURRENT request's thread_id
# 3. No way to override or inject a different thread_id
# 4. ContextVar is set by the channel, not by user input
```

---

## Code Traces

### Complete Request Flow with Code References

```python
# ═══════════════════════════════════════════════════════════════
# REQUEST FLOW: MESSAGE → RESPONSE
# ═══════════════════════════════════════════════════════════════

# 1. MESSAGE ARRIVES (Channel Layer)
# File: src/executive_assistant/channels/http.py or telegram.py

# HTTP Channel:
async def _handle_message(self, request: Request):
    request_json = await request.json()
    user_id = request_json.get("user_id")  # "telegram:123456"
    conversation_id = request_json.get("conversation_id")
    message_text = request_json.get("content")

    # Set thread_id in ContextVar
    set_thread_id(user_id)  # ← ISOLATION POINT

    # Build agent with user context
    agent = await self._build_request_agent(message_text, conversation_id, user_id)

    # Process message
    response = await agent.ainvoke({
        "messages": [HumanMessage(content=message_text)]
    })

    # Clear context
    clear_thread_id()  # ← CLEANUP

    return response


# 2. AGENT BUILT (Agent Layer)
# File: src/executive_assistant/channels/base.py:153-173

async def _build_request_agent(self, message_text: str,
                                conversation_id: str,
                                thread_id: str | None = None) -> Runnable:
    from executive_assistant.agent.langchain_agent import create_langchain_agent
    from executive_assistant.config import create_model
    from executive_assistant.tools.registry import get_all_tools
    from executive_assistant.storage.checkpoint import get_async_checkpointer
    from executive_assistant.agent.prompts import get_system_prompt

    tools = await get_all_tools()
    logger.debug("Building agent with all tools: count=%s", len(tools))

    model = create_model(model_variant)
    checkpointer = await get_async_checkpointer()

    # Build system prompt with USER'S custom prompt
    system_prompt = get_system_prompt(self.get_channel_name(), thread_id=thread_id)
    # ↑ This calls load_user_prompt(thread_id) which reads:
    #   data/users/{thread_id}/prompts/prompt.md

    return create_langchain_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        system_prompt=system_prompt,
        channel=self,
    )


# 3. SYSTEM PROMPT BUILT (Prompt Layer)
# File: src/executive_assistant/agent/prompts.py:60-95

def get_system_prompt(channel: str | None = None, thread_id: str | None = None) -> str:
    """Get appropriate system prompt for the channel.

    Merge order (highest priority last):
    1. Admin prompt (global policies)
    2. Base prompt (role definition)
    3. User prompt (personal preferences) ← USER CUSTOMIZATION
    4. Channel appendix (formatting constraints)
    """
    parts = []

    # Layer 1: Admin prompt (optional, global)
    admin_prompt = load_admin_prompt()
    if admin_prompt:
        parts.append(admin_prompt)

    # Layer 2: Base prompt (required)
    parts.append(get_default_prompt())

    # Layer 3: User prompt (optional, per-thread)
    if thread_id:
        user_prompt = load_user_prompt(thread_id)
        if user_prompt:
            parts.append(user_prompt)

    # Layer 4: Channel appendix (optional)
    appendix = get_channel_prompt(channel)
    if appendix:
        parts.append(appendix)

    return "\n\n".join(parts)


# 4. TOOL CALLED (Tool Layer)
# File: src/executive_assistant/skills/tool.py:25-70

@tool
def load_skill(skill_name: str) -> str:
    """Load a named skill guide into context (tool usage + patterns).

    Priority: User skills → Global registry

    User skills are stored in data/users/{thread_id}/skills/on_demand/
    and take precedence over system skills with the same name.
    """
    from executive_assistant.skills.loader import _parse_skill_file
    from executive_assistant.storage.user_storage import UserPaths

    registry = get_skills_registry()

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Check user skills first (if logged in)
    # ─────────────────────────────────────────────────────────────
    thread_id = get_thread_id()  # ← Returns CURRENT request's thread_id
    if thread_id:
        # Normalize skill name to filename
        normalized_name = skill_name.lower().replace(" ", "_").replace("-", "_")
        user_skill_path = UserPaths.get_skill_path(thread_id, normalized_name)

        if user_skill_path.exists():
            try:
                # Parse and return user skill
                parsed_skill = _parse_skill_file(user_skill_path)
                return f"# {parsed_skill.name.replace('_', ' ').title()} Skill (User)\n\n{parsed_skill.content}"
            except Exception as exc:
                return f"❌ Failed to load user skill '{skill_name}': {exc}"

    # ─────────────────────────────────────────────────────────────
    # STEP 2: Fall back to global registry
    # ─────────────────────────────────────────────────────────────
    normalized_name = skill_name.lower().replace(" ", "_").replace("-", "_")
    skill = registry.get(normalized_name)

    if skill:
        return f"# {skill.name.replace('_', ' ').title()} Skill\n\n{skill.content}"
    else:
        return f"❌ Skill '{skill_name}' not found."
```

---

## Comparison to Web Servers

This security model is **identical to how web servers handle multiple users**:

```python
# ═══════════════════════════════════════════════════════════════
# WEB SERVER ANALOGY (Same Process, Different Users)
# ═══════════════════════════════════════════════════════════════

# One Python process (like your agent)
# ↓
# User A logs in (session.user_id = "alice")
# → request.session.user = "alice"
# → Database query: SELECT * FROM todos WHERE user_id = 'alice'
# → Response: Alice's todos
# → Session cleared

# User B logs in (session.user_id = "bob")
# → request.session.user = "bob"  # ← Overwrites Alice's session
# → Database query: SELECT * FROM todos WHERE user_id = 'bob'
# → Response: Bob's todos (NOT Alice's!)
# → Session cleared

# SAME PROCESS, COMPLETELY ISOLATED REQUESTS!


# ═══════════════════════════════════════════════════════════════
# EXECUTIVE ASSISTANT (Same Model)
# ═══════════════════════════════════════════════════════════════

# One Python process (executive_assistant)
# ↓
# User A sends message (thread_id = "telegram:123456")
# → ContextVar: thread_id = "telegram:123456"
# → Tool call: UserPaths.get_skill_path(thread_id, "email_responses")
# → Response: User A's skill content
# → ContextVar cleared

# User B sends message (thread_id = "telegram:789012")
# → ContextVar: thread_id = "telegram:789012"  # ← Overwrites User A's
# → Tool call: UserPaths.get_skill_path(thread_id, "email_responses")
# → Response: "❌ Skill 'email_responses' not found."
# → ContextVar cleared

# SAME PROCESS, COMPLETELY ISOLATED REQUESTS!
```

### Why This is Safe

| Concern | Web Server | Executive Assistant | Safe? |
|---------|-----------|---------------------|-------|
| Same process? | ✅ Yes | ✅ Yes | ✅ Yes |
| Shared state? | ❌ No (session) | ❌ No (ContextVar) | ✅ Yes |
| User A can see User B's data? | ❌ No | ❌ No | ✅ Yes |
| Request isolation? | ✅ Per-request | ✅ Per-request | ✅ Yes |
| Memory leakage? | ❌ No | ❌ No | ✅ Yes |

---

## Security Summary

### Why There's No Cross-User Data Leakage

```python
# ═══════════════════════════════════════════════════════════════
# SECURITY PROOF: WHY USER B CANNOT ACCESS USER A'S SKILLS
# ═══════════════════════════════════════════════════════════════

# ASSUMPTION: User B wants to load User A's skill "email_responses"

# ATTACKER (User B): load_skill('email_responses')
# ↓
# TOOL EXECUTION:
#   thread_id = get_thread_id()  # → "telegram:789012" (User B's ID)
#   path = UserPaths.get_skill_path(thread_id, skill_name)
#   # → data/users/telegram:789012/skills/on_demand/email_responses.md
# ↓
# FILE SYSTEM CHECK:
#   if path.exists():  # ← FALSE (User A's skill is in different directory!)
# ↓
# RESULT: "❌ Skill 'email_responses' not found."
# ↑ LLM has NO knowledge that User A has this skill!


# ═══════════════════════════════════════════════════════════════
# WHY THERE'S NO CODE PATH TO ACCESS OTHER USERS' DATA
# ═══════════════════════════════════════════════════════════════

# 1. All paths use: data/users/{thread_id}/...
#    → thread_id comes from ContextVar (request-specific)

# 2. No function accepts "other_thread_id" parameter
#    → load_skill(skill_name) ← No thread_id parameter!
#    → create_user_skill(...) ← No thread_id parameter!
#    → All tools use get_thread_id() internally

# 3. No "list_all_users_skills()" function exists
#    → No enumeration attack possible

# 4. File system permissions (optional extra layer)
#    chmod 700 data/users/telegram:123456/  # Owner-only access
```

### Three Layers of Security

1. **Path Isolation** (File System)
   - Each user has unique directory: `data/users/{thread_id}/`
   - Different paths = No overlap possible

2. **Context Isolation** (Runtime)
   - `ContextVar` ensures thread-local state
   - Each request has its own `thread_id`
   - No shared state between requests

3. **Conversation Isolation** (LLM Memory)
   - Checkpointer scoped by `thread_id`
   - Each user sees only their own history
   - LLM doesn't "remember" other users' data

### Key Security Properties

| Property | Implementation | Result |
|----------|---------------|--------|
| Stateless processing | Fresh agent per request | No memory leakage |
| Thread-local context | `ContextVar` for `thread_id` | No shared state |
| Deterministic paths | `data/users/{thread_id}/...` | No path confusion |
| Request-scoped history | Checkpointer keyed by `thread_id` | No conversation leakage |
| No enumeration | No "list all users" function | No data discovery |
| No injection | Tools don't accept `thread_id` param | No ID injection |

---

## Conclusion

**Yes, it's the same agent process, but that's safe because:**

1. **Stateless processing**: Each request builds a fresh agent with the current user's `thread_id`
2. **Thread-local context**: `ContextVar` ensures each request has its own isolated `thread_id`
3. **Path isolation**: File paths are deterministic: `data/users/{thread_id}/skills/...`
4. **No cross-user code paths**: No function accepts or searches for "other user" data
5. **Checkpointer scoping**: Conversation history is keyed by `thread_id` in PostgreSQL

The LLM doesn't "remember" User A's skills because:
- System prompt is rebuilt per-request (includes only User B's custom prompt)
- Tools access `thread_id` dynamically via `get_thread_id()`
- No global state persists between requests

**This is identical to how web servers handle multiple users** - one process, many isolated requests. The security comes from **request-scoped context**, not separate processes.

---

## Additional Security Considerations

### Optional Hardening

```bash
# Set file system permissions (optional extra layer)
chmod 700 data/users/
find data/users/ -type d -exec chmod 700 {} \;  # Owner-only directories
find data/users/ -type f -exec chmod 600 {} \;  # Owner-only files

# Result: Even if process is compromised, files are protected by OS permissions
```

### Audit Logging

```python
# Consider adding audit logs for sensitive operations
import logging

audit_logger = logging.getLogger("audit")

@tool
def create_user_skill(name: str, description: str, content: str) -> str:
    thread_id = get_thread_id()

    # Log skill creation
    audit_logger.info(
        "User skill created",
        extra={
            "thread_id": thread_id,
            "skill_name": normalized_name,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # ... rest of implementation
```

### Monitoring

```python
# Consider adding metrics for security monitoring
from prometheus_client import Counter

skill_load_attempts = Counter(
    "skill_load_attempts_total",
    "Total number of skill load attempts",
    ["thread_id", "skill_name", "success"]
)

@tool
def load_skill(skill_name: str) -> str:
    thread_id = get_thread_id()
    try:
        # ... load logic
        skill_load_attempts.labels(
            thread_id=thread_id,
            skill_name=skill_name,
            success="true"
        ).inc()
    except Exception:
        skill_load_attempts.labels(
            thread_id=thread_id,
            skill_name=skill_name,
            success="false"
        ).inc()
```

---

**Document Version**: 1.0
**Last Updated**: 2026-01-29
**Maintained By**: Executive Assistant Development Team
