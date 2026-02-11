# Memory Management - Updating & Deleting

When users want to change or remove stored memories, follow these efficient workflows.

## Core Principle

**Always list first, then act.** Don't guess memory IDs - users can see the list and confirm.

## Workflows

### Remove a Memory

**User says:** "Remove that memory", "Delete this", "Forget X", "Clear that"

**Steps:**
1. List memories to find the target: `list_memories()`
2. Delete using ID from list: `update_memory(memory_id="[ID]", status="deleted")`
3. Confirm action to user

**Example:**
```
User: "Remove the timezone memory"
Agent:
1. list_memories()
   → Shows: "ID: abc-123... | Type: preference | Key: timezone | Content: Timezone: Australia/Sydney"
2. update_memory(memory_id="abc-123-def4-5678...", status="deleted")
3. "Removed the timezone memory. Is there anything you'd like me to remember instead?"
```

**DO NOT:**
- ❌ Call `delete_memory()` or `forget_memory()` without the ID
- ❌ Call `search_memories()` first (list_memories is faster)
- ❌ Guess or infer the ID

### Update Memory Content

**User says:** "Change that memory", "Update X to Y", "Actually I prefer Z"

**Steps:**
1. List memories to find the target: `list_memories()`
2. Update using ID from list: `update_memory(memory_id="[ID]", content="[new content]")`
3. Confirm the change

**Example:**
```
User: "Update my timezone to EST"
Agent:
1. list_memories()
   → Shows: "ID: abc-123... | Key: timezone | Content: Timezone: Australia/Sydney"
2. update_memory(memory_id="abc-123-def4-5678...", content="Timezone: EST")
3. "Updated your timezone to EST."
```

**Alternative (if memory has a key):**
```
normalize_or_create_memory(key="timezone", content="Timezone: EST")
```

**DO NOT:**
- ❌ Create a new memory without removing the old one (causes duplicates)
- ❌ Call `create_memory()` with the same key (won't work as expected)

### Replace Memory with Different Type

**User says:** "That's actually a fact not a preference", "Make this a style instead"

**Steps:**
1. List memories to find the target: `list_memories()`
2. Update with new type: `update_memory(memory_id="[ID]", content="[content]", memory_type="[new type]")`
   - Note: `update_memory()` only changes content/status. For type changes, use delete + recreate:
3. Delete old: `update_memory(memory_id="[ID]", status="deleted")`
4. Create new: `create_memory(content="[content]", memory_type="[new type]", key="[key]")`

**Example:**
```
User: "That communication preference is actually a constraint"
Agent:
1. list_memories()
   → Shows: "ID: abc-123... | Type: style | Key: communication | Content: Professional tone"
2. update_memory(memory_id="abc-123-def4-5678...", status="deleted")
3. create_memory("Must use professional tone", "constraint", "communication")
4. "Changed communication from a style preference to a constraint."
```

## Memory Types Reference

| Type | Use For | Example |
|------|----------|---------|
| `profile` | User identity | Name, role, responsibilities |
| `preference` | User choices | "Prefers dark mode", "Likes brief summaries" |
| `fact` | Objective information | "Lives in New York", "Works at Acme Corp" |
| `constraint` | Requirements/limitations | "Must use Python", "Cannot work on weekends" |
| `style` | Communication format | "Professional tone", "Casual language" |
| `context` | Situational info | "Working on Q1 project", "On vacation until..." |

## Quick Reference

| User Request | Action | Tool |
|--------------|--------|------|
| "Remove X" | List, then delete | `list_memories()` → `update_memory(id, status="deleted")` |
| "Change X to Y" | List, then update | `list_memories()` → `update_memory(id, content=Y)` |
| "Update my [key]" | Update by key | `normalize_or_create_memory(key, new_content)` |
| "What do you remember?" | List all | `list_memories()` |
| "Forget X" | Same as remove | `list_memories()` → `update_memory(id, status="deleted")` |

## Common Mistakes

### Mistake 1: Searching Instead of Listing

❌ **Wrong:**
```
search_memories("timezone")
# → Returns full memory details, harder to parse ID
```

✅ **Right:**
```
list_memories()
# → Shows clean table with truncated IDs
```

### Mistake 2: Creating Duplicate Instead of Updating

❌ **Wrong:**
```
User: "Change my timezone to EST"
create_memory("Timezone: EST", "preference", "timezone")
# → Now has TWO timezone memories!
```

✅ **Right:**
```
list_memories()
# → Find existing timezone memory ID
update_memory(memory_id="[ID]", content="Timezone: EST")
```

### Mistake 3: Using delete/forget Without ID

❌ **Wrong:**
```
delete_memory("timezone")
# → "Memory not found" (expects UUID, not key)
```

✅ **Right:**
```
list_memories()
# → Get full UUID from list
update_memory(memory_id="abc-123-def4-5678...", status="deleted")
```

## Response Patterns

**After removing a memory:**
- ✅ "Removed the [topic] memory."
- ✅ "Cleared that from memory."
- ✅ "Deleted the [type] memory."

**After updating a memory:**
- ✅ "Updated your [topic] to [new value]."
- ✅ "Changed [topic] from [old] to [new]."
- ✅ "Memory updated: [brief description]."

**When memory not found:**
- ✅ "I don't see a memory about [topic]. Would you like me to list all memories?"
- ✅ "No [topic] memory found. Here's what I have:" (then list)

## Important Notes

- **Always list first** - users can identify which memory to change
- **Use update_memory for deletions** - it's clearer than delete_memory/forget_memory
- **Use normalize_or_create_memory for key-based updates** - when you know the key
- **Don't create duplicates** - update existing memories instead
- **Confirm the action** - tell users what changed
