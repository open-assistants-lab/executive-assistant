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
    """Generate 10 test queries per persona, covering ALL available tools.

    Each query may trigger multiple tools. Total tool coverage across 10 test cases:
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
    ]

    # Apply persona style transformations
    if style == "terse":
        queries = [q.split(",")[0][:60] for q in base_queries]
    elif style == "formal":
        queries = [f"could you please {q.lower()}?" for q in base_queries]
    elif style == "casual":
        queries = [
            f"hey, {q.lower()} please" if i % 2 == 0 else f"can u {q.lower()}?"
            for i, q in enumerate(base_queries)
        ]
    elif style == "inquisitive":
        queries = [
            f"{q}? how does that work?" if i % 3 == 0 else f"can you help me {q.lower()}?"
            for i, q in enumerate(base_queries)
        ]
    elif style == "narrative":
        queries = [
            f"i need to {q.lower()}" if i % 2 == 0 else f"been meaning to {q.lower()}, can you?"
            for i, q in enumerate(base_queries)
        ]
    elif style == "authoritative":
        queries = [
            f"{q.upper()} - DO IT NOW!" if i % 2 == 0 else f"execute: {q}"
            for i, q in enumerate(base_queries)
        ]
    elif style == "expressive":
        queries = [
            f"🌟 {q} 🌟" if i % 2 == 0 else f"hey! {q.lower()} please!"
            for i, q in enumerate(base_queries)
        ]
    elif style == "minimal":
        queries = [
            "email + contacts + todos",
            "email list/search/read",
            "contacts + send email",
            "todos CRUD",
            "files list/read/write/edit/delete",
            "file search glob/grep",
            "shell + files",
            "memory + todos",
            "time + todos",
            "skills + web",
        ]
    elif style == "technical":
        queries = [f"execute {q} with default params" for q in base_queries]
    elif style == "uncertain":
        queries = [
            f"i don't know how to {q.lower()}, can you help?"
            if i % 2 == 0
            else f"could you help me {q.lower()}? confused."
            for i, q in enumerate(base_queries)
        ]
    else:
        queries = base_queries

    return queries[:10]
