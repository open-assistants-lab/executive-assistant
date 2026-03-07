"""Persona definitions for agent evaluation."""

PERSONAS = [
    {
        "id": "p1",
        "name": "Direct Dave",
        "description": "Short, terse commands. No small talk. Get to the point.",
        "style": "terse",
        "sample_phrases": [
            "list my emails",
            "find contact John",
            "send email to bob@gmail.com",
            "what files in docs?",
            "sync my inbox",
        ],
        "system_prompt_addition": "Respond in short, direct sentences. No pleasantries.",
    },
    {
        "id": "p2",
        "name": "Polite Pam",
        "description": "Very polite, uses please and thank you. Formal language.",
        "style": "formal",
        "sample_phrases": [
            "Could you please list my emails?",
            "Would you be so kind as to find my contact John?",
            "I would like to send an email please.",
            "Thank you for checking my files.",
            "I appreciate your help with syncing my inbox.",
        ],
        "system_prompt_addition": "Use polite, formal language. Include please and thank you.",
    },
    {
        "id": "p3",
        "name": "Casual Chris",
        "description": "Casual, informal. Uses slang and abbreviations. Relaxed tone.",
        "style": "casual",
        "sample_phrases": [
            "hey can u list my emails?",
            "find john for me",
            "send that email to bob",
            "what files we got?",
            "sync my inbox plz",
        ],
        "system_prompt_addition": "Use casual, friendly language. Can be informal.",
    },
    {
        "id": "p4",
        "name": "Questioning Quinn",
        "description": "Asks questions. Wants clarification. Inquires before acting.",
        "style": "inquisitive",
        "sample_phrases": [
            "Can you show me my emails? Which folder do you mean?",
            "I need to find a contact - what's the best way?",
            "How do I send an email?",
            "What files do I have access to?",
            "What's the current sync status?",
        ],
        "system_prompt_addition": "Ask clarifying questions when needed. Show curiosity.",
    },
    {
        "id": "p5",
        "name": "Storytelling Sam",
        "description": "Explains context. Gives background. Narrative style.",
        "style": "narrative",
        "sample_phrases": [
            "I was expecting an email from John about the project, can you check?",
            "Let me tell you about this contact I met - her name is Sarah...",
            "So I need to send an update to the team about...",
            "I've been working on some documents and wanted to see...",
            "My inbox has been crazy lately, can you help sync?",
        ],
        "system_prompt_addition": "Acknowledge context and background. Show understanding.",
    },
    {
        "id": "p6",
        "name": "Commanding Chris",
        "description": "Authoritative. Gives commands. Expects immediate action.",
        "style": "authoritative",
        "sample_phrases": [
            "List all emails now.",
            "Find contact John immediately.",
            "Send email to bob@gmail.com - urgent.",
            "Show me all files in docs.",
            "Sync inbox right away.",
        ],
        "system_prompt_addition": "Respond with clear action items. Be decisive.",
    },
    {
        "id": "p7",
        "name": "Emoji Eva",
        "description": "Uses emojis. Expressive. Visual communication.",
        "style": "expressive",
        "sample_phrases": [
            "Hey! 📧 Can you list my emails?",
            "Find John 🙋‍♂️ for me please!",
            "Send that email 📤 to Bob",
            "What files do we have? 📁",
            "Sync my inbox 🔄",
        ],
        "system_prompt_addition": "Use emojis appropriately to enhance communication.",
    },
    {
        "id": "p8",
        "name": "Minimalist Mike",
        "description": "Extremely brief. Single words or very short phrases.",
        "style": "minimal",
        "sample_phrases": [
            "emails",
            "John",
            "email bob",
            "files",
            "sync",
        ],
        "system_prompt_addition": "Keep responses extremely brief. One-liners only.",
    },
    {
        "id": "p9",
        "name": "Technical Terry",
        "description": "Uses technical terms. Precise. Details-oriented.",
        "style": "technical",
        "sample_phrases": [
            "Execute email_list for current user with default parameters.",
            "Query contacts table for John Smith record.",
            "Send SMTP message to bob@gmail.com with subject 'Update'.",
            "List filesystem contents of /docs directory.",
            "Trigger IMAP sync for inbox folder.",
        ],
        "system_prompt_addition": "Use precise technical language. Be specific about parameters.",
    },
    {
        "id": "p10",
        "name": "Confused Clara",
        "description": "Uncertain. Asks for help. Needs guidance.",
        "style": "uncertain",
        "sample_phrases": [
            "I don't know how to check my emails... can you help?",
            "I think I need to find a contact but I'm not sure how?",
            "How do I even send an email?",
            "What files do I have? I'm lost.",
            "Can you help me sync? I've never done this.",
        ],
        "system_prompt_addition": "Be patient and helpful. Offer guidance and explain steps clearly.",
    },
    # Additional 10 personas for comprehensive testing
    {
        "id": "p11",
        "name": "Analytical Alex",
        "description": "Data-driven. Asks for metrics. Wants numbers and facts.",
        "style": "analytical",
        "sample_phrases": [
            "What's my email open rate?",
            "How many contacts do I have?",
            "Show me todo completion statistics",
            "What files were modified today?",
            "What's my memory usage?",
        ],
        "system_prompt_addition": "Provide data-driven responses with metrics and numbers.",
    },
    {
        "id": "p12",
        "name": "Efficient Eddie",
        "description": "Optimizes for speed. Wants shortcuts. Results-focused.",
        "style": "efficient",
        "sample_phrases": [
            "Quick - sync my email",
            "Fastest way to find John?",
            "Send update email NOW",
            "List files quick",
            "Brief todo status",
        ],
        "system_prompt_addition": "Be concise and result-focused. Prioritize speed.",
    },
    {
        "id": "p13",
        "name": "Verbose Victor",
        "description": "Very detailed. Explains everything. Comprehensive responses.",
        "style": "verbose",
        "sample_phrases": [
            "Could you please explain in detail how to check my emails?",
            "I'd like a comprehensive overview of my contacts.",
            "Please provide a thorough explanation of the email sending process.",
            "Give me all the details about my files.",
            "I need a complete breakdown of my todos.",
        ],
        "system_prompt_addition": "Provide comprehensive, detailed responses. Don't skip details.",
    },
    {
        "id": "p14",
        "name": "Curious Casey",
        "description": "Asks follow-ups. Wants to learn. Explores options.",
        "style": "curious",
        "sample_phrases": [
            "What if I wanted to filter by date?",
            "Can I also search by subject?",
            "What other options do I have?",
            "Is there a way to export this?",
            "Why did you choose that approach?",
        ],
        "system_prompt_addition": "Offer options and alternatives. Explain trade-offs.",
    },
    {
        "id": "p15",
        "name": "Busy Brian",
        "description": "Multi-tasking. Gives multiple tasks at once.",
        "style": "busy",
        "sample_phrases": [
            "While I check email, search contacts",
            "List files AND sync inbox",
            "Add todo AND send email",
            "Search web while I read this",
            "Create subagent AND schedule task",
        ],
        "system_prompt_addition": "Handle multiple tasks efficiently. Parallelize when possible.",
    },
    {
        "id": "p16",
        "name": "Organized Olivia",
        "description": "Structures everything. Lists and categories. Orderly.",
        "style": "organized",
        "sample_phrases": [
            "Group my contacts by category",
            "Organize todos by priority",
            "List files in folders",
            "Categorize my emails",
            "Sort by date",
        ],
        "system_prompt_addition": "Organize information clearly. Use lists and categories.",
    },
    {
        "id": "p17",
        "name": "Flexible Fran",
        "description": "Adaptable. Changes mind. Goes with flow.",
        "style": "flexible",
        "sample_phrases": [
            "Actually, let's do emails instead of files",
            "Maybe just a quick summary",
            "Whichever works best",
            "I'm not sure, you decide",
            "Whatever approach you prefer",
        ],
        "system_prompt_addition": "Be flexible. Adapt to changing requirements smoothly.",
    },
    {
        "id": "p18",
        "name": "Goal-Oriented Gary",
        "description": "Focuses on outcomes. Tracks progress. Milestones.",
        "style": "goal_oriented",
        "sample_phrases": [
            "What's the progress on my tasks?",
            "Show me completion rate",
            "What milestones can we track?",
            "Any blockers?",
            "Next steps?",
        ],
        "system_prompt_addition": "Track progress toward goals. Highlight milestones and blockers.",
    },
    {
        "id": "p19",
        "name": "Collaborative Carol",
        "description": "Team-focused. Considers others. Shares context.",
        "style": "collaborative",
        "sample_phrases": [
            "Share with the team",
            "CC my manager",
            "Add to shared folder",
            "Team visibility please",
            "Who should be included?",
        ],
        "system_prompt_addition": "Consider team collaboration. Suggest sharing options.",
    },
    {
        "id": "p20",
        "name": "Privacy-First Paul",
        "description": "Security conscious. Minimizes data. Careful sharing.",
        "style": "privacy",
        "sample_phrases": [
            "Don't log this",
            "Keep it private",
            "Don't share externally",
            "Is this secure?",
            "Delete after use",
        ],
        "system_prompt_addition": "Prioritize privacy and security. Minimize data exposure.",
    },
]


# Test cases mapping: 10 test cases per persona, covering ALL tools
# Tool coverage: 20+ tools across all test cases
TEST_CASES = {
    # Test case index -> (query, tools_expected)
    1: ("Connect my Gmail account with password test123", ["email_connect"]),
    2: ("Search my inbox for quarterly report emails", ["email_search"]),
    3: ("Find and read the most recent email", ["email_get"]),
    4: ("Send email to team@example.com about update", ["email_send"]),
    5: ("Search contacts for Smith", ["contacts_search"]),
    6: ("Add new contact Charlie with email charlie@startup.com", ["contacts_add"]),
    7: ("List all my todos", ["todos_list"]),
    8: ("Add a new todo for meeting tomorrow", ["todos_add"]),
    9: ("List files in my directory", ["files_list"]),
    10: ("Read the README.txt file", ["files_read"]),
}


def get_persona(persona_id: str) -> dict | None:
    """Get persona by ID."""
    for p in PERSONAS:
        if p["id"] == persona_id:
            return p
    return None


def get_all_personas() -> list[dict]:
    """Get all personas."""
    return PERSONAS


def generate_test_queries(persona: dict, count: int = 10) -> list[str]:
    """Generate test queries per persona, covering ALL available tools.

    Each query may trigger multiple tools. Total tool coverage across test cases:
    - email_connect, email_list, email_search, email_get, email_send
    - contacts_list, contacts_search, contacts_add, contacts_update, contacts_delete
    - todos_list, todos_add, todos_update, todos_delete, todos_extract
    - files_list, files_read, files_write, files_edit, files_delete
    - files_glob_search, files_grep_search
    - shell_execute
    - memory_get_history, memory_search
    - time_get
    - skills_list, skills_load
    - search_web, scrape_url, map_url, crawl_url
    - subagent_create, subagent_invoke, subagent_schedule

    For count > 10, repeats queries with variations.
    """
    style = persona["style"]

    # Multi-step queries that cover many tools
    base_queries = [
        # 1. Email + Contacts + Todos (5+ tools)
        "Connect Gmail account, search emails from John, add him to contacts, create follow-up todo",
        # 2. Email operations (3 tools)
        "List my recent emails, search for meeting invites, read the latest one",
        # 3. Email send + Contacts (2 tools)
        "Find contact for Alice, send her an email about the project update",
        # 4. Todos CRUD (4 tools)
        "List all todos, add new todo for tomorrow, mark urgent ones, delete completed",
        # 5. Files operations (5 tools)
        "List files in directory, read README, write meeting notes, edit typos, delete temp files",
        # 6. File search (2 tools)
        "Find all Python files modified this week, grep for TODO comments",
        # 7. Shell + Files (2 tools)
        "Run python script to list files, save output to results.txt",
        # 8. Memory + Todos (3 tools)
        "Search conversation history for project discussions, create todos for action items",
        # 9. Time + Todos (2 tools)
        "Get current time, schedule a todo reminder for 2 hours from now",
        # 10. Skills + Web (4 tools)
        "List available skills, load SQL skill, search web for latest tech news, summarize findings",
        # 11. Subagent operations (3 tools)
        "Create a research subagent, invoke it to find info, schedule follow-up",
        # 12. Contacts CRUD (4 tools)
        "List contacts, add new contact Bob, update his email, delete old contact",
        # 13. Web scraping (3 tools)
        "Search web for AI news, scrape top article, map related pages",
        # 14. Email sync + extract (2 tools)
        "Sync my inbox, extract todos from recent emails",
        # 15. Shell commands (2 tools)
        "Check current directory, run date command",
    ]

    # Apply persona style transformations
    def style_query(q: str, idx: int) -> str:
        if style == "terse":
            return q.split(",")[0][:60]
        elif style == "formal":
            return f"could you please {q.lower()}?"
        elif style == "casual":
            return f"hey, {q.lower()} please" if idx % 2 == 0 else f"can u {q.lower()}?"
        elif style == "inquisitive":
            return f"{q}? how does that work?" if idx % 3 == 0 else f"can you help me {q.lower()}?"
        elif style == "narrative":
            return (
                f"i need to {q.lower()}"
                if idx % 2 == 0
                else f"been meaning to {q.lower()}, can you?"
            )
        elif style == "authoritative":
            return f"{q.upper()} - DO IT NOW!" if idx % 2 == 0 else f"execute: {q}"
        elif style == "expressive":
            return f"🌟 {q} 🌟" if idx % 2 == 0 else f"hey! {q.lower()} please!"
        elif style == "minimal":
            words = {
                0: "email + contacts + todos",
                1: "email list/search/read",
                2: "contacts + send email",
                3: "todos CRUD",
                4: "files list/read/write/edit/delete",
                5: "file search glob/grep",
                6: "shell + files",
                7: "memory + todos",
                8: "time + todos",
                9: "skills + web",
                10: "subagent create/invoke/schedule",
                11: "contacts CRUD",
                12: "web scrape/search",
                13: "email sync + extract",
                14: "shell commands",
            }
            return words.get(idx % 15, "task")
        elif style == "technical":
            return f"execute {q} with default params"
        elif style == "uncertain":
            return (
                f"i don't know how to {q.lower()}, can you help?"
                if idx % 2 == 0
                else f"could you help me {q.lower()}? confused."
            )
        elif style == "analytical":
            return f"give me metrics: {q.lower()}"
        elif style == "efficient":
            return f"fast: {q.lower()}"
        elif style == "verbose":
            return f"please provide comprehensive details about {q.lower()}"
        elif style == "curious":
            return f"what if I wanted to {q.lower()}? also how about {q.lower().split()[0]}?"
        elif style == "busy":
            return f"while doing this, also {q.lower()}"
        elif style == "organized":
            return f"group and organize: {q.lower()}"
        elif style == "flexible":
            return f"actually, let's try {q.lower()} instead"
        elif style == "goal_oriented":
            return f"track progress: {q.lower()} - what's the status?"
        elif style == "collaborative":
            return f"share with team: {q.lower()}"
        elif style == "privacy":
            return f"do this privately: {q.lower()} - don't log"
        return q

    # Generate queries with variations for count > 10
    queries = []
    for i in range(count):
        base_idx = i % len(base_queries)
        q = base_queries[base_idx]
        # Add variation for repeated queries
        if i >= len(base_queries):
            variations = [
                f"also {q.lower()}",
                f"again: {q.lower()}",
                f"repeat: {q.lower()}",
                f"once more: {q.lower()}",
            ]
            q = f"{variations[i % len(variations)]}"
        queries.append(style_query(q, i))

    return queries[:count]
