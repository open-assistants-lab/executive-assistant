# Improved User Customization Plan

## Executive Summary

This document provides a critical analysis of the three user customization features (MCP, Prompts, Skills) and proposes a more cohesive, phased implementation strategy.

---

## Part 1: Critical Analysis of Existing Plans

### 1.1 User MCP Plan Analysis

**Strengths:**
- ✅ Mirrors Claude Desktop UX (local vs remote)
- ✅ Comprehensive command set (/mcp add, list, remove, etc.)
- ✅ Security-conscious (confirmation prompts, allowlists)

**Issues & Concerns:**

🔴 **Complexity Risk: MCP tool loading is not trivial**
- MCP servers return dynamic tool schemas at runtime
- Need to merge user MCP tools with global 71-tool registry
- Tool name collisions possible (e.g., two "search" tools)
- MCP servers can crash/hang — need timeout + isolation

🔴 **No Hot-Reload Strategy**
- "Hot reload without restart" is mentioned but **how?**
- Current agent creation happens once at startup
- Tools are baked into the agent graph — cannot be changed post-creation
- **Critical**: LangChain agents are **not designed for dynamic tool addition**

🟡 **OAuth Complexity**
- Remote MCP OAuth is a whole feature in itself
- Token storage, refresh flows, revoke handling
- Recommend: defer to Phase 2

🟡 **Storage Schema Mismatch**
- Plan mentions `mcp.json` with `type: "stdio" | "http"`
- But langchain-mcp uses different config format
- Need adapter layer or standardize on one format

**Missing:**
- MCP server health checking
- Tool call audit logging (mentioned but not detailed)
- Fallback strategy when MCP server is unavailable

---

### 1.2 User Prompt Plan Analysis

**Strengths:**
- ✅ Simple storage model (single markdown file)
- ✅ Size cap (1-2k chars) prevents token abuse
- ✅ Clear merge order: Admin → Base → User → Channel

**Issues & Concerns:**

🟡 **Merge Order Contradiction**
- Plan says: "Admin → Base → User → Channel"
- But in main.py:187-190, current order is: Admin → Base (then channel appended later)
- **Clarify needed**: Should user prompt override admin prompt?
  - Option A: Admin → Base → **User** → Channel (user can override admin)
  - Option B: Admin → User → Base → Channel (admin final authority)
  - **Recommendation**: Option A with safety overrides

🔴 **No Validation of "Harmful" Prompts**
- Plan mentions "don't allow override of safety policies"
- But **no implementation strategy** for this
- How to detect jailbreak attempts in user prompt?
- **Recommendation**: Basic keyword blocking + post-merge safety check

🟡 **Caching Strategy Unclear**
- "Cache per thread with mtime check" — where?
- File I/O on every request is expensive
- **Recommendation**: In-memory cache with TTL (e.g., 60s)

**Missing:**
- Prompt versioning (for rollback)
- Prompt templates (variables like {name}, {timezone})
- Multi-line input handling for `/prompt set`

---

### 1.3 User Skills Plan Analysis

**Strengths:**
- ✅ Reuses existing skill loader logic
- ✅ Observer → Evolve pattern is innovative
- ✅ Thread-scoped storage matches existing pattern

**Issues & Concerns:**

🟡 **Observer → Evolve Complexity**
- This is **two major features** in one:
  1. Simple user skill creation (easy)
  2. Observer → Evolve pipeline (complex)
- Recommend: split into Phase 1 (creation) and Phase 2 (evolution)

🔴 **"Hot-Load" Terminology Confusion**
- Skills are already "hot-loaded" via `load_skill` tool
- User skills would just extend this pattern
- **No restart needed** — this is already how skills work!

🟡 **Skill Name Collision Risk**
- User creates skill named "planning"
- But system skill "planning" already exists
- Which one takes precedence?
- **Recommendation**: User skills override system skills (with warning)

**Missing:**
- Skill deletion/management commands
- Skill validation (max size, format)
- Skill inheritance (user skill extending system skill)

---

## Part 2: Architectural Concerns

### 2.1 The "Hot Reload" Fallacy

**Critical Realization**: The plans mention "hot reload without restart" for both MCP and skills, but this is **misleading**.

**Current Architecture:**
```
[Startup] → Build Agent → Bake in 71 tools → Start listening
```

**What "Hot Reload" Actually Means:**
- Skills: ✅ Already hot-loaded via `load_skill` tool (no restart needed)
- MCP: ❌ **Cannot** add tools to running agent without rebuild

**For MCP, We Have Two Options:**

**Option A: Agent Rebuild (Expensive)**
```
User adds MCP → Detect change → Rebuild agent → Replace in registry
```
- Pros: Clean architecture
- Cons: Slow (5-10s), disrupts ongoing conversations

**Option B: Dynamic Tool Router (Complex)**
```
Create a "mcp_proxy" tool that routes to user MCP servers at runtime
```
- Pros: No agent rebuild
- Cons: Loses tool schema benefits (LLM can't see MCP tool signatures)

**Recommendation**: Start with Option A (simple), optimize to Option B later if needed.

---

### 2.2 Storage Path Consistency

All three plans use `data/users/{thread_id}/`, which is good! But we need to standardize:

```
data/users/{thread_id}/
├── prompts/          # User prompts
│   └── prompt.md
├── skills/           # User skills (on-demand)
│   └── on_demand/
│       └── *.md
├── mcp/              # User MCP configs
│   ├── local.json    # stdio servers
│   └── remote.json   # http/sse servers
├── files/            # (existing)
├── tdb/              # (existing)
└── vdb/              # (existing)
```

**Recommendation**: Create a shared `user_storage.py` module for path management.

---

### 2.3 Command Explosion Risk

Current commands: `/mem`, `/reminder`, `/vdb`, `/tdb`, `/adb`, `/file`, `/meta`, `/user`, `/flow`

Planned additions: `/mcp` (7 subcommands), `/prompt` (4 subcommands), `/skill` (3+ subcommands)

**Total**: 9 base commands + ~14 subcommands = **23+ commands**

**User Experience Concern:**
- Too many commands = cognitive overload
- Similar patterns (`/vdb list`, `/mcp list`, `/skill list` — confusing!)
- Telegram bot command limit is 100, but discoverability is the real issue

**Recommendation**: Group into meta-commands:
- `/config` → handles prompts, MCP, skills
- `/storage` → handles vdb, tdb, files
- Keep only essential: `/mem`, `/reminder`, `/reset`, `/debug`, `/meta`

---

## Part 3: Improved Implementation Plan

### Phase 1: Foundation (Week 1-2)

**Goal**: Build storage + management infrastructure for all three features.

#### 1.1 User Storage Module
```python
# src/executive_assistant/storage/user_storage.py
class UserPaths:
    """Centralized path management for user-scoped data."""

    @staticmethod
    def get_user_root(thread_id: str) -> Path:
        return settings.USERS_ROOT / thread_id

    @staticmethod
    def get_prompt_path(thread_id: str) -> Path:
        return UserPaths.get_user_root(thread_id) / "prompts" / "prompt.md"

    @staticmethod
    def get_skills_dir(thread_id: str) -> Path:
        return UserPaths.get_user_root(thread_id) / "skills" / "on_demand"

    @staticmethod
    def get_mcp_local_path(thread_id: str) -> Path:
        return UserPaths.get_user_root(thread_id) / "mcp" / "local.json"

    @staticmethod
    def get_mcp_remote_path(thread_id: str) -> Path:
        return UserPaths.get_user_root(thread_id) / "mcp" / "remote.json"
```

#### 1.2 User Prompt System
**Priority**: **HIGHEST** (simplest, highest value)

**Implementation:**
1. Add `load_user_prompt(thread_id)` function to `prompts.py`
2. Update `get_system_prompt()` in `channels/base.py` to include user prompt
3. Add `/prompt` commands to `management_commands.py`

**Merge Order:**
```
Admin Prompt → Base Prompt → User Prompt → Channel Appendix
```

**Safety Check:**
```python
def _safety_check(prompt: str) -> bool:
    """Basic safety check for user prompts."""
    forbidden_patterns = [
        "ignore previous instructions",
        "disregard all rules",
        "jailbreak",
        # ... more patterns
    ]
    prompt_lower = prompt.lower()
    return not any(p in prompt_lower for p in forbidden_patterns)
```

**Estimated Effort**: 2-3 days

---

#### 1.3 User Skills System
**Priority**: MEDIUM (extends existing pattern)

**Implementation:**
1. Extend `skills/loader.py` to check user skills directory first
2. Add `create_user_skill` tool
3. (Optional) Add `/skill list` command

**Load Order:**
```python
def load_skill(name: str) -> str | None:
    thread_id = get_thread_id()
    if thread_id:
        # Check user skills first
        user_skill_path = UserPaths.get_skills_dir(thread_id) / f"{name}.md"
        if user_skill_path.exists():
            return _parse_skill_file(user_skill_path).content
    # Fallback to global registry
    return skills_registry.get(name)
```

**Estimated Effort**: 2-3 days

---

### Phase 2: User MCP (Local Only) (Week 3-4)

**Goal**: Add local MCP server support (stdio only, defer remote/OAuth).

#### 2.1 MCP Config Storage
```python
# data/users/{thread_id}/mcp/local.json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {"BRAVE_API_KEY": "..."}
    }
  }
}
```

#### 2.2 MCP Integration Strategy
**Use Agent Rebuild Approach (Option A)**:

1. Add `/mcp` commands (add, list, remove, download)
2. On MCP config change → trigger agent rebuild for that thread
3. Store per-thread agent instances in cache

```python
# Per-thread agent cache
_thread_agent_cache: dict[str, Runnable] = {}

async def get_or_build_agent(thread_id: str) -> Runnable:
    if thread_id in _thread_agent_cache:
        mtime = UserPaths.get_mcp_local_path(thread_id).stat().st_mtime
        cache_mtime = _thread_agent_cache[f"{thread_id}_mtime"]
        if mtime <= cache_mtime:
            return _thread_agent_cache[thread_id]

    # Rebuild agent with new MCP tools
    agent = await _build_agent_for_thread(thread_id)
    _thread_agent_cache[thread_id] = agent
    _thread_agent_cache[f"{thread_id}_mtime"] = mtime
    return agent
```

**Estimated Effort**: 4-5 days

---

### Phase 3: Advanced Features (Week 5+)

**Defer to future iterations:**

3.1 **Remote MCP (HTTP/SSE)**
- OAuth flow
- Token storage
- Health checks

3.2 **Observer → Evolve for Skills**
- Instinct capture
- Clustering algorithm
- Draft skill generation
- HITL approval flow

3.3 **Prompt Templates**
- Variable substitution
- Multi-language support

---

## Part 4: Success Criteria

### Phase 1 (Foundation)
- [ ] User can set/view/clear prompt via `/prompt set/show/clear`
- [ ] Prompt is applied on next message without restart
- [ ] User can create skill via `create_user_skill` tool
- [ ] `load_skill` loads user skills if they exist
- [ ] All user data under `data/users/{thread_id}/`

### Phase 2 (User MCP)
- [ ] User can add/list/remove local MCP servers via `/mcp`
- [ ] MCP tools appear in agent tool list
- [ ] MCP server failures don't crash the agent
- [ ] Per-thread agent cache invalidates on config change

### Phase 3 (Advanced)
- [ ] Remote MCP servers work via `/mcp connect`
- [ ] Observer captures user behavior patterns
- [ ] Evolve proposes draft skills based on instincts
- [ ] User can approve/reject skill evolution

---

## Part 5: Testing Strategy

### Unit Tests
```python
# tests/test_user_storage.py
def test_user_paths():
    thread_id = "telegram:123"
    assert UserPaths.get_prompt_path(thread_id) == Path("data/users/telegram:123/prompts/prompt.md")

# tests/test_user_prompts.py
def test_load_user_prompt():
    # Write test prompt
    # Load and verify
    # Test caching

# tests/test_user_skills.py
def test_user_skill_override():
    # Create user skill "planning"
    # Verify it overrides system skill
```

### Integration Tests
```python
# tests/test_user_mcp_integration.py
async def test_mcp_server_addition():
    # Add MCP server via command
    # Rebuild agent
    # Verify tool count increased
    # Call MCP tool
    # Clean up
```

### Manual Testing Checklist
- [ ] Create user prompt → send message → verify tone change
- [ ] Set prompt to 2000 chars → verify rejection
- [ ] Create user skill → load in same session → verify content
- [ ] Add MCP server → list tools → call tool → remove server
- [ ] Test with 3 concurrent users → verify isolation

---

## Part 6: Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| MCP server crash hangs agent | HIGH | MEDIUM | Timeout (30s), isolate in subprocess |
| User prompt jailbreak | HIGH | LOW | Keyword blocking, post-merge safety check |
| Tool name collisions | MEDIUM | HIGH | Namespace prefix (e.g., "mcp.filesystem.read") |
| Per-thread agent memory leak | MEDIUM | MEDIUM | LRU cache (max 100 threads), TTL |
| File I/O performance | LOW | MEDIUM | In-memory cache with 60s TTL |

---

## Part 7: Open Questions

1. **Prompt Override Policy**: Should user prompt be able to override admin prompt?
   - **Recommendation**: Yes, but with safety check for policy violations.

2. **Agent Rebuild Performance**: If user adds MCP, how to handle ongoing conversations?
   - **Recommendation**: Let current message finish with old agent, next message uses new agent.

3. **MCP Tool Namespace**: How to handle name conflicts (e.g., two "search" tools)?
   - **Recommendation**: Prefix with server name: `mcp.{server_name}.{tool_name}`.

4. **Skill Evolution Approval**: How to present draft skills to user?
   - **Recommendation**: Send as file in Telegram, user edits and re-uploads.

5. **Backward Compatibility**: What if existing users have data in old paths?
   - **Recommendation**: Migration script in main.py startup.

---

## Part 8: Recommended Implementation Order

### Week 1: User Prompts (Quick Win)
- Day 1-2: Storage + commands
- Day 3: Integration with prompt assembly
- Day 4-5: Testing + documentation

### Week 2: User Skills (Extension)
- Day 1-2: Extend loader
- Day 3: Create tool
- Day 4-5: Testing + documentation

### Week 3-4: User MCP (Complex)
- Day 1-3: Config storage + commands
- Day 4-7: Agent rebuild mechanism
- Day 8-10: Testing + error handling
- Day 11-14: Documentation + polish

### Week 5+: Advanced Features
- Observer → Evolve
- Remote MCP
- Optimization

---

## Conclusion

The original plans are ambitious but have several architectural gaps:

1. **MCP "hot reload" is not feasible** without agent rebuild (need to clarify expectations)
2. **Prompt safety validation is missing** (add keyword blocking)
3. **Command explosion risk** (consider grouping into `/config`)
4. **Observer → Evolve is too complex** for Phase 1 (split into phases)

**Recommended Approach**: Implement in phases, starting with simplest (prompts), then skills (extension), then MCP (complex). This allows iterative learning and risk mitigation.

**Next Steps**:
1. Review and approve improved plan
2. Set up feature branch structure
3. Start Phase 1 (User Prompts)
