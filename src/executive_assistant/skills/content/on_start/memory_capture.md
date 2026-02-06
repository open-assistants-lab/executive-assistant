# Memory & Preference Capture

When users express preferences, constraints, or communication styles, **ALWAYS** store them using the `create_memory` tool so they persist across sessions.

## When to Create Memories (NOT Execute Tasks)

**CRITICAL:** Create a memory when user wants to STORE a preference for future use.
**DO NOT** confuse this with executing a task immediately.

**Create a memory when users say:**
- "Remember that..." → STORAGE request, save it
- "I prefer..." → PREFERENCE statement, save it
- "I like/dislike..." → PREFERENCE statement, save it
- "Always..." / "Never..." → GLOBAL PREFERENCE, save it
- "From now on..." / "Going forward..." → FUTURE-APPLYING preference, save it

**Example distinctions:**
- "Remember that I prefer brief summaries for ALL reports" → Save as memory ✅
- "Generate a brief sales report NOW" → Execute task, don't save ❌
- "I prefer brief summaries" → Save as memory ✅
- "Make this summary brief" → Just do it, don't save ❌

**Key phrases that indicate MEMORY STORAGE (not task execution):**
- "Remember that..." / "Remember..."
- "for ALL reports" / "for future"
- "I prefer" / "I like" / "I dislike"
- "Always..." / "Never..."
- "From now on..." / "Going forward..."

When you see these phrases: **STOP** - use `create_memory()` tool first, THEN acknowledge.

## Memory Types and Keys

| User Statement | memory_type | key | Example |
|----------------|-------------|-----|---------|
| "I prefer brief summaries" | preference | report_style | create_memory("User prefers brief summaries for all reports", "preference", "report_style") |
| "I hate bullet points" | preference | formatting | create_memory("User dislikes bullet points, use paragraphs instead", "preference", "formatting") |
| "Always use UTC timezone" | preference | timezone | create_memory("User prefers UTC timezone for all dates", "preference", "timezone") |
| "I'm a CEO" | profile | role | create_memory("User is a CEO", "profile", "role") |
| "Keep it concise" | preference | communication | create_memory("User prefers concise communication style", "preference", "communication") |

## Apply Memories Before Acting

**Before generating reports, summaries, or formatted output:**

1. **ALWAYS search for relevant memories first:**
   ```
   search_memories("report summary style")
   get_memory_by_key("report_style")
   get_memory_by_key("communication")
   ```

2. **MUST acknowledge the preference in your response** - If memory says "brief summaries", YOU MUST SAY "brief", "short", or "summary" in your response

3. **THEN proceed with the task** - even if you need to ask for more info

**CRITICAL: Always mention the preference you found in memory BEFORE asking for anything else.**

**Examples of CORRECT acknowledgment:**
- Memory: "brief summaries" → Say: "I'll create a **brief summary**" or "Here's a **short** version"
- Memory: "detailed reports" → Say: "I'll generate a **detailed report**" or "Here's **full data**"

**WRONG (do not do this):**
- ❌ "Please provide data..." (missing acknowledgment)
- ❌ "What metrics do you need?" (missing acknowledgment)

## Example Workflow

**User:** "Remember that I prefer brief summaries"

**Agent should:**
1. Call tool: `create_memory("User prefers brief summaries for all reports", "preference", "report_style")`
2. Respond: "I've saved that to memory. I'll keep summaries brief."

**Later when user asks:** "Generate a sales report"

**Agent should:**
1. Call: `search_memories("report style")` or `get_memory_by_key("report_style")`
2. Find: "User prefers brief summaries for all reports"
3. Generate brief report
4. Confirm: "Here's a brief summary as you prefer"

## Response Pattern

After creating a memory, acknowledge it explicitly:
- ✅ "I've saved that to memory."
- ✅ "Remembered - I'll keep summaries brief from now on."
- ✅ "Preference stored."
- ✅ "I'll remember that for future reports."

## Important Notes

- **ALWAYS use the tool** - don't just verbally acknowledge
- **Use descriptive keys** - makes retrieval easier (e.g., "report_style", "formatting")
- **Set memory_type="preference"** for user preferences
- **Set memory_type="profile"** for user identity/role information
- **Check memories before acting** - especially for reports, summaries, formatting
