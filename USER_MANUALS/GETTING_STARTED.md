# Getting Started with Ken Executive Assistant

Welcome! This guide will help you get started with Ken, your AI-powered executive assistant.

## First Steps

### 1. Say Hello
Simply start chatting:
```
You: Hi!
Ken: Hello! 👋 I'm your Executive Assistant. I can help you:
       • Track work and timesheets
       • Analyze data with SQL/Python
       • Store and retrieve knowledge
       • Set reminders and manage goals

       What would you like help with?
```

### 2. Ken Will Learn About You
On your first interaction, Ken will ask a few questions to understand your role and preferences:
```
Ken: I'd like to learn about you to serve you better.

     1. What's your name?
     2. What's your role? (Developer, Manager, Analyst, etc.)
     3. What are your main goals? (Track work, analyze data, automate tasks)
     4. Any preferences? (concise responses, detailed explanations)
```

**This is a one-time setup** - Ken will remember your profile for all future conversations.

---

## What Can Ken Do For You?

### 📊 Track Your Work
Simply tell Ken what you worked on:
```
You: I worked on the sales dashboard for 3 hours
Ken: ✅ Logged: "Worked on sales dashboard" (3 hours)
```

### 🧠 Remember Things
Store important information for later:
```
You: Remember: The API key is sk-xxxxx
Ken: ✅ Saved: "API key: sk-xxxxx"
```

### 📅 Set Reminders
Never forget important tasks:
```
You: Remind me to review PRs at 3pm every weekday
Ken: ✅ Created recurring reminder: "Review PRs" at 3:00 PM (weekdays)
```

### 🔍 Find Information
Search through past conversations and stored knowledge:
```
You: What did we decide about the API pricing?
Ken: Found 3 relevant documents:
     1. "API Pricing Decision" (Jan 15): "Enterprise tier: 10,000 req/min..."
     2. "Pricing Strategy Discussion" (Feb 3): "Freemium model with..."
```

### 📈 Analyze Data
Upload files and ask questions:
```
You: I have sales.csv with 50K rows. Show me top 10 products by revenue
Ken: ✅ Analyzing sales data...
     Top 10 Products by Revenue:
     1. Widget Pro - $45,234
     2. Premium Pack - $38,912
     ...
```

### 🐍 Run Python
Execute calculations and data processing:
```
You: Calculate the compound interest on $10,000 at 5% for 10 years
Ken: ✅ Running Python calculation...
     Result: $16,288.95
```

---

## Essential Commands

### Memory Commands
```bash
/mem list                          # See all stored memories
/mem add budget: $5000            # Add a memory
/mem search "project"             # Search memories
```

### Reminder Commands
```bash
/reminder list                     # See all reminders
/reminder set 3pm "meeting"       # Set one-time reminder
/reminder set 9am "standup" --daily  # Set recurring reminder
```

### Database Commands
```bash
/tdb list                          # See all tables
/tdb create users                  # Create a new table
/tdb query users "SELECT * FROM users"  # Query data
```

### File Commands
```bash
/file list                         # See all files
/file read notes.txt               # Read a file
/file write report.md "content"    # Write a file
```

### Debug Mode
```bash
/debug on                          # See detailed progress
/debug off                         # Clean mode
```

---

## Tips for Best Results

### ✅ Do This:
- **Be specific**: "Summarize the Q3 sales report" works better than "summarize"
- **Use natural language**: Just ask questions like you would a human assistant
- **Provide context**: "The file is in /reports/2024/" helps Ken find it
- **Give feedback**: "Actually, use bullet points" helps Ken learn your preferences

### ❌ Avoid This:
- **Don't worry about technical details**: Ken figures out which tools to use
- **Don't memorize commands**: You can use natural language instead
- **Don't start over**: Ken remembers everything across conversations

---

## Advanced Features (Discover Over Time)

### 🧠 Skills System
Ken can learn from your conversations and develop reusable skills:
```bash
evolve_instincts                   # Turn conversation patterns into skills
list_skills                        # See available skills
load_skill analytics               # Load a specific skill
```

### 📚 Knowledge Base
Store documents and search by meaning:
```bash
/vdb create docs                   # Create knowledge base
/vdb add docs "Meeting notes..."  # Add document
/vdb search docs "API decisions"   # Semantic search
```

### 🎯 Goals
Track objectives with progress monitoring:
```bash
/goals create "Launch dashboard"   # Create goal
/goals progress "Launch dashboard" 50  # Update progress
/goals list                        # See all goals
```

---

## Quick Examples

### Example 1: Daily Work Tracking
```
You: I worked on the user authentication feature for 4 hours
Ken: ✅ Logged: "Worked on user authentication" (4 hours)

You: Create a timesheet for this week
Ken: ✅ Timesheet created:
     Mon: 4h (user authentication)
     Tue: 3h (database optimization)
     Wed: 5h (API integration)
     Total: 12 hours
```

### Example 2: Data Analysis
```
You: I uploaded sales_data.csv. Show me monthly trends
Ken: ✅ Analyzing sales data...

     Monthly Sales Trends:
     Jan: $45,230 (+12% vs prev month)
     Feb: $51,890 (+15%)
     Mar: $58,450 (+13%)

     💡 Trend: Consistent 13% month-over-month growth
```

### Example 3: Research Helper
```
You: What did we decide about the database migration?
Ken: Found 2 relevant discussions:

     1. "Migration Planning" (Jan 10):
        "Decision: Migrate to PostgreSQL in Q2, use dual-write strategy"

     2. "Rollback Plan" (Jan 15):
        "Keep MySQL backup for 30 days post-migration"
```

---

## Getting Help

### Ask Ken Directly
```
You: What can you do?
You: How do I set reminders?
You: Show me all commands
```

### Check Storage
```
/meta                              # See overview of all storage
/meta files                        # See file count and size
/meta tdb                          # See database tables
```

### Debug Mode
```
/debug on                          # Enable detailed progress
```

---

## Next Steps

1. **Start using Ken** for simple tasks (logging work, setting reminders)
2. **Store important information** (API keys, decisions, preferences)
3. **Explore data analysis** (upload CSVs, ask questions)
4. **Discover advanced features** (skills, goals, knowledge base)

Ken learns from your conversations and gets better over time. The more you use it, the more helpful it becomes!

---

**Need more?**
- See [ESSENTIAL_COMMANDS.md](ESSENTIAL_COMMANDS.md) for complete command reference
- See [MEMORY_AND_KNOWLEDGE.md](MEMORY_AND_KNOWLEDGE.md) for memory system details
- See [CONVERSATION_TO_SKILL.md](CONVERSATION_TO_SKILL.md) for advanced learning features
