# Rename Discussion: "Memory" → Semantic (LangChain Alignment)

**Current Issue**: The term "memory" is generic and may cause confusion for admins/devs.

**Better Approach**: Align with LangChain's established terminology for consistency.

---

## Problem Analysis

### Why "Memory" is Confusing

1. **Generic term**: "Memory" is used in many contexts:
   - Computer memory (RAM)
   - Storage/disk memory
   - Other AI "memory" systems
   - General concept of remembering

2. **Technical ambiguity**: When devs see "memory.db", they might think:
   - Is this system RAM usage?
   - Is this a cache?
   - Is this related to computer memory?

3. **Non-descriptive**: Doesn't convey what data it stores:
   - User facts (name, role, preferences)
   - Profile information
   - Static user data

---

## Proposed Names

### Option 1: **profile** ✅ (RECOMMENDED)

**Pros**:
- ✅ Clear meaning: user profile information
- ✅ Common in web apps: "user profile"
- ✅ Fits the data: names, roles, preferences
- ✅ Short and simple
- ✅ Developers understand immediately

**Cons**:
- ⚠️ "profile" sometimes implies editable UI fields
- ⚠️ Might conflict if other "profile" systems exist

**Example**: `profile.db`, `profile_storage.py`, `get_profile()`

---

### Option 2: **identity**

**Pros**:
- ✅ Descriptive: stores who the user is
- ✅ Matches the pillar's purpose: "Who you are"
- ✅ Professional sounding
- ✅ Distinct from technical terms

**Cons**:
- ⚠️ Slightly longer than "profile"
- ⚠️ May feel too formal for some contexts

**Example**: `identity.db`, `identity_storage.py`, `get_identity()`

---

### Option 3: **user_data**

**Pros**:
- ✅ Very clear: data about the user
- ✅ Hard to misunderstand
- ✅ Flexible for future expansion

**Cons**:
- ❌ Generic (just replaces one generic term with another)
- ❌ Longer to type
- ❌ Doesn't convey semantic meaning

**Example**: `user_data.db`, `user_data_storage.py`, `get_user_data()`

---

### Option 4: **facts**

**Pros**:
- ✅ Accurate: stores facts about user
- ✅ Short and simple
- ✅ Distinguishes from feelings/opinions

**Cons**:
- ⚠️ "facts" can feel impersonal
- ⚠️ Doesn't capture preferences well
- ⚠️ Might confuse with "fact" checking

**Example**: `facts.db`, `facts_storage.py`, `get_facts()`

---

### Option 5: **context**

**Pros**:
- ✅ Related to purpose: provides context
- ✅ AI/LLM terminology ("context window")
- ✅ Flexible for future expansion

**Cons**:
- ❌ Very generic (similar problem as "memory")
- ❌ Overloaded term in AI
- ❌ Doesn't distinguish from journal/instincts context

**Example**: `context.db`, `context_storage.py`, `get_context()`

---

## Recommendation

### **Option 1: "profile"** (RECOMMENDED) ✅

**Rationale**:
1. **Clear meaning**: Every web dev understands "user profile"
2. **Accurate**: Stores exactly what a user profile contains
3. **Short**: Easy to type and remember
4. **Familiar**: Common pattern across applications
5. **Consistent**: Aligns with "user profile" concept

**File Examples**:
```
data/users/http_http_alice/profile/
└── profile.db                    (was mem.db)

src/executive_assistant/storage/profile_storage.py
get_profile()                      (was get_mem_storage())
```

---

## Migration Impact

### Files to Rename (if "profile" is chosen):

**Storage**:
- `mem_storage.py` → `profile_storage.py`
- `mem.db` → `profile.db`

**Functions**:
- `get_mem_storage()` → `get_profile_storage()`
- `_get_relevant_memories()` → `_get_relevant_profile()`

**Variable Names**:
- `memory` → `profile`
- `memories` → `profile_data`

**Config**:
- `memory:` → `profile:` in config.yaml

**Tests**:
- All test files and test names
- 12 tests in test_memory_retrieval_fix.py
- 12 tests in test_memory_integration.py

**Documentation**:
- All markdown files mentioning "memory"
- Comments in code
- API documentation

---

## Comparison Table

| Name | Clear? | Unique? | Short? | Familiar? | Score |
|------|--------|---------|-------|-----------|-------|
| **profile** | ✅ | ✅ | ✅ | ✅ | 5/5 |
| identity | ✅ | ✅ | ⚠️ | ⚠️ | 3/5 |
| user_data | ✅ | ✅ | ❌ | ✅ | 3/5 |
| facts | ✅ | ✅ | ✅ | ⚠️ | 3/5 |
| context | ❌ | ❌ | ✅ | ⚠️ | 2/5 |
| **memory** (current) | ❌ | ❌ | ✅ | ⚠️ | 2/5 |

---

## Four Pillars with "Profile"

After renaming, the four pillars become:

1. **Profile**: "Who you are" (Declarative knowledge)
   - Name: Alice, PM at Acme
   - Role: Sales analytics
   - Preferences: Brief responses

2. **Journal**: "What you did" (Episodic knowledge)
   - Feb 4: Created work_log table
   - Weekly: Built sales dashboard
   - Activity history

3. **Instincts**: "How you behave" (Procedural knowledge)
   - Reports → Use bullet points
   - Morning → Be detailed
   - Sales → Suggest visualizations

4. **Goals**: "Why/Where" (Future intentions)
   - Launch dashboard by EOM
   - Complete API integration
   - Learn Python basics

---

## Decision Matrix

| Criteria | Profile | Identity | User Data | Facts | Keep Memory |
|----------|---------|----------|----------|-------|-------------|
| Clarity | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| Distinctiveness | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| Brevity | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Familiarity | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Accuracy | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **TOTAL** | **25/25** | **20/25** | **20/25** | **20/25** | **14/25** |

---

## Recommendation: Use "profile"

**Winner**: **profile** ✅

**Benefits**:
- Maximum clarity and familiarity
- Industry-standard terminology
- Accurate description of the data
- Easy migration path

**Alternative if "profile" conflicts**: **identity** (second best)

---

## Ready to Proceed?

Please confirm:
1. Should we proceed with renaming "memory" → "profile"?
2. Or do you prefer another name from the list?
3. Or keep "memory" as-is?

Once confirmed, I can:
- Create migration script
- Update all references
- Run tests to verify
- Commit changes
- Update documentation
