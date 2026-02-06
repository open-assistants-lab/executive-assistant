# Memory and Knowledge System

Ken's memory system is designed to remember everything important - facts, decisions, conversations, and patterns. This guide explains how it works.

---

## 🧠 The 4-Pillar Memory System

Ken uses **four types of memory**, each serving a different purpose:

### 1. Semantic Memory (VDB) - "Who you are"
**What it stores:** Decisions, context, knowledge, preferences
**How it works:** Meaning-based search (finds by intent, not just keywords)
**Use for:**
- Meeting notes and decisions
- Project documentation
- API keys and configurations
- User preferences

**Example:**
```
You: Remember: We decided to use PostgreSQL for the new project
Ken: ✅ Saved: "Decision: Use PostgreSQL for new project"

You: What did we decide about the database?
Ken: Found relevant memory:
     "Decision: Use PostgreSQL for the new project" (stored 2 days ago)
```

---

### 2. Structured Memory (TDB) - "What you can query"
**What it stores:** Tabular data (SQL-queryable)
**How it works:** SQLite database
**Use for:**
- Timesheets and logs
- Contact lists
- Configuration tables
- Reference data

**Example:**
```
You: Create a timesheets table and add my work today
Ken: ✅ Created table: timesheets
     Inserted: {"date": "2024-01-15", "project": "dashboard", "hours": 4}

You: Show me my total hours this week
Ken: Query results: 32 hours
```

---

### 3. Episodic Memory (Journal) - "What you did"
**What it stores:** Activity log with timestamps
**How it works:** Automatic tracking of all actions
**Use for:**
- "What did I work on last Tuesday?"
- Timesheet generation
- Progress tracking

**Example:**
```
You: What did I work on last week?
Ken: Found 23 activities from last week:
     • Created dashboard schema (Jan 15, 2pm)
     • Analyzed sales data (Jan 16, 10am)
     • Fixed API bug (Jan 17, 3pm)
```

---

### 4. Procedural Memory (Instincts) - "How you behave"
**What it stores:** Behavioral patterns and preferences
**How it works:** Learns from corrections and repetitions
**Use for:**
- Communication style (concise vs detailed)
- Format preferences (JSON, bullets, tables)
- Response patterns

**Example:**
```
You: Be concise
You: Use bullet points
You: Actually, use JSON for data

[Ken learns pattern and applies automatically]
```

---

## 💾 Storing Information

### Quick Memory Storage

**Single fact:**
```
You: Remember: The API key is sk-xxxxx
Ken: ✅ Saved: "API key: sk-xxxxx"
```

**Complex information:**
```
You: Remember these project details:
    - Name: Project Alpha
    - Deadline: March 15
    - Budget: $50,000
    - Team: Alice, Bob, Carol

Ken: ✅ Saved 4 memories:
     1. Project Alpha name
     2. Project Alpha deadline
     3. Project Alpha budget
     4. Project Alpha team
```

---

### Structured Data Storage

**Create a table:**
```
You: Create a contacts table
Ken: ✅ Created table: contacts
     Add data with: insert into contacts ...
```

**Import from file:**
```
You: Import sales.csv to a table
Ken: ✅ Imported 1,234 rows to: sales_data
```

---

### Document Storage

**Store a document:**
```
You: Save this to knowledge base:
    "Meeting Date: Jan 15, 2024
     Attendees: John, Sarah, Mike
     Decision: Launch product on March 1st
     Rationale: Market research shows strong demand"

Ken: ✅ Added to knowledge base (collection: documents)
     You can search this later with: /vdb search documents "product launch"
```

---

## 🔍 Retrieving Information

### Semantic Search (Find by Meaning)

**Search memories:**
```
You: What do we know about the API?
Ken: Found 3 relevant memories:

     1. "API Decision" (Jan 10)
        "Decision: Use REST API with JSON responses"

     2. "API Key" (Jan 12)
        "Production API key: sk-xxxxx"

     3. "API Rate Limits" (Jan 14)
        "Rate limit: 1000 req/min, burstable to 5000"
```

**Search documents:**
```
You: Find documents about pricing decisions
Ken: Found 2 relevant documents:

     1. "Pricing Strategy Meeting" (Jan 15)
        "Decision: Freemium model with $29/month premium tier"
        Similarity: 0.94

     2. "Competitor Analysis" (Jan 10)
        "Competitors charge $25-50/month"
        Similarity: 0.87
```

---

### Query Data (SQL)

**Query structured data:**
```
You: Show me all timesheets from this week
Ken: Query results:
     | date       | project    | hours |
     |------------|------------|-------|
     | 2024-01-15 | dashboard  | 4     |
     | 2024-01-16 | api        | 3     |
     | 2024-01-17 | bugfix     | 5     |
```

**Join data:**
```
You: Show me total hours by project
Ken: Query results:
     | project    | total_hours |
     |------------|-------------|
     | dashboard  | 12          |
     | api        | 8           |
     | bugfix     | 10          |
```

---

## 🎯 Advanced Features

### Automatic Learning

Ken learns your preferences automatically:

**Pattern 1: Communication Style**
```
You: Be concise
[Ken uses concise responses]

You: Give me more detail
[Ken provides detailed explanations]

[Ken learns: "User prefers concise for summaries, detailed for explanations"]
```

**Pattern 2: Format Preferences**
```
You: Use JSON
[Ken uses JSON format]

You: Use bullet points
[Ken uses bullets]

[Ken learns: "User prefers JSON for data, bullets for lists"]
```

**Pattern 3: Workflow Patterns**
```
You: Always query the production database first
[Ken learns: "Prefer production_db over test_db"]

You: Show me top 10 products by revenue
[Ken automatically runs: SELECT * FROM products ORDER BY revenue DESC LIMIT 10]
```

---

### Conversation → Skill

Over time, Ken can convert learned patterns into reusable skills:

**Step 1: Build patterns through conversations**
```
Conversation 1:
You: Summarize the sales data
Ken: [Provides summary]

Conversation 2:
You: What's the executive summary?
Ken: [Provides summary]

Conversation 3:
You: Give me highlights only
Ken: [Provides concise summary]
```

**Step 2: Evolve patterns into skills**
```
You: evolve_instincts
Ken: Generated 1 draft skill:
     communication_concise (85% confidence)
     Description: User prefers concise summaries

     Approve with: approve_evolved_skill('communication_concise')
```

**Step 3: Approve the skill**
```
You: approve_evolved_skill('communication_concise')
Ken: ✅ Skill saved! All future responses will follow this pattern.
```

---

### Cross-Conversation Memory

Ken remembers across conversations:

**Conversation 1:**
```
You: Remember: My manager is Sarah Johnson
Ken: ✅ Saved
```

**Conversation 2 (weeks later):**
```
You: Who should I notify about the deployment?
Ken: Based on your stored memories, your manager is Sarah Johnson.
     Should I notify her?
```

---

## 📊 Memory Storage Hierarchy

```
data/
├── shared/              # Organization-wide (scope="shared")
│   ├── vdb/            # Shared knowledge base
│   ├── tdb/            # Shared tables
│   └── files/          # Shared files
└── users/              # Your personal data (scope="context")
    └── {your_thread}/
        ├── vdb/        # Your knowledge base
        ├── tdb/        # Your tables
        ├── journal/    # Your activity log
        ├── mem/        # Your memories
        └── instincts/  # Your learned patterns
```

**Privacy:**
- Your personal data is **thread-isolated** by default
- Only you can access your personal data
- Admins can create shared resources for everyone

---

## 🔒 Memory Persistence

### What Survives Thread Resets?

✅ **Persists:**
- All memories (/mem add)
- All tables and data (/tdb create)
- All knowledge base documents (/vdb add)
- All files (/file write)
- All learned patterns (instincts)

❌ **Cleared:**
- Current conversation messages (chat history)

### What Survives Service Restarts?

✅ **Everything persists** across restarts:
- Memories, tables, documents, files, instincts
- Reminders (scheduled in PostgreSQL)
- Goals and progress tracking

---

## 💡 Best Practices

### ✅ Do This

**Be specific when storing:**
```
Good: Remember: Project Alpha API key is sk-xxxxx
Bad: Remember: the api key
```

**Use meaningful categories:**
```
Good: Remember: production_db password is ...
Good: Remember: staging_db password is ...
Bad: Remember: database password is ...
```

**Store decisions with context:**
```
Good: Remember: We chose PostgreSQL because it has better JSON support
Bad: Remember: use postgresql
```

**Query with natural language:**
```
You: What did we decide about the database?
You: Show me the timesheet from last Tuesday
You: Find documents about pricing strategy
```

### ❌ Avoid This

**Don't store sensitive passwords:**
```
⚠️ Risky: Remember: My banking password is ...
✅ Better: Use secure vault for credentials
```

**Don't store redundant info:**
```
Redundant: Remember: The project name is Project Alpha
Redundant: Remember: Project Alpha is the project name
```

**Don't worry about forgetting commands:**
```
You: I forgot the command for searching memories
Ken: You can use: /mem search "keyword"
   Or just ask: "Search for memories about X"
```

---

## 📈 Memory Growth Over Time

As you use Ken, it learns and remembers more:

**Week 1:**
- 10-20 memories (basic facts, preferences)
- 1-2 tables (timesheets, simple data)
- 5-10 documents (meeting notes, decisions)

**Month 1:**
- 50-100 memories (rich context, decisions)
- 5-10 tables (ongoing projects)
- 50+ documents (comprehensive knowledge base)

**Month 3+:**
- 200+ memories (deep contextual understanding)
- 10+ tables (complex data relationships)
- 200+ documents (organizational knowledge)
- Learned skills (conversation patterns automated)

---

## 🎓 Summary

**Ken's memory system is designed to:**
1. **Remember what you tell it** (semantic memory)
2. **Store structured data** (transactional memory)
3. **Track what you do** (episodic memory)
4. **Learn how you work** (procedural memory)

**You get better results by:**
- Storing important information explicitly
- Using natural language queries
- Letting Ken learn your preferences
- Evolving patterns into skills

**Over time, Ken becomes:**
- More personalized (learns your style)
- More knowledgeable (accumulates context)
- More automated (patterns become skills)

---

**Need more?**
- See [GETTING_STARTED.md](GETTING_STARTED.md) for introduction
- See [ESSENTIAL_COMMANDS.md](ESSENTIAL_COMMANDS.md) for command reference
- See [CONVERSATION_TO_SKILL.md](CONVERSATION_TO_SKILL.md) for advanced learning features
