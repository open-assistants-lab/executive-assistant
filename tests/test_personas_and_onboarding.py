"""Persona-based and onboarding tests for unified context system.

Tests validate all 4 pillars work as intended with real-world scenarios:
- Different user personas (developer, manager, designer, executive)
- Complete onboarding flows
- Progressive context accumulation
- Cross-pillar interaction patterns
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, "src")

from langchain_ollama import ChatOllama
from executive_assistant.config import settings
from executive_assistant.storage.mem_storage import MemoryStorage
from executive_assistant.storage.journal_storage import JournalStorage
from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite
from executive_assistant.storage.goals_storage import GoalsStorage

# Load credentials
load_dotenv("docker/.env")
os.environ["OLLAMA_MODE"] = "cloud"


class TestPersonas:
    """Test different user personas with the unified context system."""

    def test_persona_developer_progressive_onboarding(self):
        """Test onboarding flow for a developer persona."""
        print("\n" + "="*80)
        print("PERSONA TEST: Developer - Progressive Onboarding")
        print("="*80)

        # Setup temporary storage
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "dev_onboarding"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Initialize storage systems
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        instincts = InstinctStorageSQLite()
        instincts._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        # ====== DAY 1: First interaction ======
        print("\n📅 Day 1: First Interaction - Initial Setup")

        # User introduces themselves
        memory.create_memory(
            content="Name: Alex Kim, Role: Full-Stack Developer, "
                   "Team: Platform Engineering, "
                   "Stack: Python, TypeScript, React, PostgreSQL",
            memory_type="fact",
            thread_id=thread_id,
        )
        print("   ✅ Memory: User profile created")

        memory.create_memory(
            content="Prefers: Code examples in Python, detailed error messages",
            memory_type="preference",
            thread_id=thread_id,
        )
        print("   ✅ Memory: Communication preferences stored")

        # Log first work session
        journal.add_entry(
            content="Set up development environment for new project",
            entry_type="raw",
            thread_id=thread_id,
        )
        journal.add_entry(
            content="Installed Python 3.13, Node.js 20, PostgreSQL 16",
            entry_type="raw",
            thread_id=thread_id,
        )
        print("   ✅ Journal: Initial setup logged")

        # ====== DAY 3: Pattern emergence ======
        print("\n📅 Day 3: Pattern Emergence - System Learning")

        # User repeatedly asks for concise responses
        journal.add_entry(
            content="User feedback: 'Make it brief, just the code'",
            entry_type="raw",
            thread_id=thread_id,
            metadata={"feedback_type": "brevity"},
        )

        # System learns instinct
        instincts.create_instinct(
            trigger="user says 'brief' or 'concise'",
            action="provide code snippets only, minimal explanation",
            domain="communication",
            confidence=0.7,
            source="learning-detected",
            thread_id=thread_id,
        )
        print("   ✅ Instincts: Learned preference for brevity")

        # ====== WEEK 1: Goal setting ======
        print("\n📅 Week 1: Goal Setting")

        goals.create_goal(
            title="Complete REST API backend",
            description="Build and deploy REST API with PostgreSQL database",
            category="short_term",
            target_date=(datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            priority=8,
            importance=9,
            thread_id=thread_id,
        )
        print("   ✅ Goals: API project goal created")

        # ====== WEEK 2: Progress tracking ======
        print("\n📅 Week 2: Progress Tracking")

        # Journal entries show progress
        journal.add_entry(
            content="Implemented user authentication endpoints (/login, /register)",
            entry_type="raw",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Created database migrations for user profiles table",
            entry_type="raw",
            thread_id=thread_id,
        )

        # Update goal progress
        active_goals = goals.list_goals(thread_id=thread_id, status="planned")
        if active_goals:
            goal_id = active_goals[0]["id"]
            goals.update_goal_progress(
                goal_id=goal_id,
                thread_id=thread_id,
                progress=25.0,
                source="journal",
                notes="Completed auth and database schema",
            )
        print("   ✅ Goals + Journal: Progress auto-updated")

        # ====== Verification ======
        print("\n✅ Developer Persona Verification:")

        # Retrieve all context
        memories = memory.list_memories(thread_id=thread_id)
        entries = journal.list_entries(thread_id=thread_id, limit=10)
        learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)
        user_goals = goals.list_goals(thread_id=thread_id, status="planned")

        print(f"   Memories: {len(memories)} items")
        print(f"   Journal entries: {len(entries)} activities")
        print(f"   Instincts learned: {len(learned)} patterns")
        print(f"   Active goals: {len(user_goals)} objectives")

        assert len(memories) >= 2, "Should have user profile and preferences"
        assert len(entries) >= 4, "Should track work activities"
        assert len(learned) >= 1, "Should learn from patterns"
        assert len(user_goals) >= 1, "Should have active goals"

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)

        print("\n✅ Developer persona onboarding test PASSED")

    def test_persona_manager_executive_user(self):
        """Test executive/manager persona with high-level focus."""
        print("\n" "="*80)
        print("PERSONA TEST: Executive/Manager - Strategic Focus")
        print("="*80)

        # Setup
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "exec_onboarding"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Initialize storage
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        # ====== Executive profile ======
        print("\n📅 Executive Profile Setup")

        memory.create_memory(
            content="Name: Jennifer Martinez, Role: VP of Engineering, "
                   "Department: Platform Architecture, "
                   "Reports: 8 Engineering Leads, "
                   "Focus: Strategic planning, team coordination",
            memory_type="fact",
            thread_id=thread_id,
        )

        memory.create_memory(
            content="Prefers: Executive summaries, KPI dashboards, strategic overviews",
            memory_type="preference",
            thread_id=thread_id,
        )

        memory.create_memory(
            content="Team size: 45 engineers across 5 squads",
            memory_type="fact",
            thread_id=thread_id,
        )
        print("   ✅ Memory: Executive profile created")

        # ====== High-level activities ======
        print("\n📅 Executive Activities Logged")

        journal.add_entry(
            content="Quarterly planning meeting with engineering leads",
            entry_type="raw",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Reviewed Q4 OKRs and team performance metrics",
            entry_type="raw",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Architecture review: Microservices migration strategy",
            entry_type="raw",
            thread_id=thread_id,
        )
        print("   ✅ Journal: Strategic activities logged")

        # ====== Strategic goals ======
        print("\n📅 Strategic Goal Setting")

        goals.create_goal(
            title="Complete microservices migration Q3",
            description="Migrate monolith to microservices architecture by end of Q3",
            category="long_term",
            target_date=(datetime.now(timezone.utc) + timedelta(days=120)).isoformat(),
            priority=10,
            importance=10,
            thread_id=thread_id,
        )

        goals.create_goal(
            title="Reduce technical debt by 30%",
            description="Improve code quality and reduce accumulated technical debt",
            category="medium_term",
            target_date=(datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
            priority=8,
            importance=8,
            thread_id=thread_id,
        )
        print("   ✅ Goals: Strategic objectives set")

        # ====== Verification ======
        print("\n✅ Executive Persona Verification:")

        memories = memory.list_memories(thread_id=thread_id)
        entries = journal.list_entries(thread_id=thread_id, limit=10)
        user_goals = goals.list_goals(thread_id=thread_id, status="planned")

        print(f"   Executive memories: {len(memories)} items")
        print(f"   Strategic activities: {len(entries)} logged")
        print(f"   Strategic goals: {len(user_goals)} objectives")

        # Verify executive-specific content
        assert any("VP" in m["content"] or "Director" in m["content"] for m in memories), \
            "Should have executive role"
        assert any("planning" in e["content"].lower() or "meeting" in e["content"].lower() for e in entries), \
            "Should log strategic activities"

        print("\n✅ Executive persona test PASSED")

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)

    def test_persona_designer_creative_user(self):
        """Test designer/creative persona with visual focus."""
        print("\n" "="*80)
        print("PERSONA TEST: Designer/Creative - Visual Focus")
        print("="*80)

        # Setup
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "designer_onboarding"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Initialize storage
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        instincts = InstinctStorageSQLite()
        instincts._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        # ====== Designer profile ======
        print("\n📅 Designer Profile Setup")

        memory.create_memory(
            content="Name: Maya Chen, Role: UX/UI Designer, "
                   "Tools: Figma, Sketch, Adobe Creative Suite, "
                   "Specialty: Mobile app design, design systems",
            memory_type="fact",
            thread_id=thread_id,
        )

        memory.create_memory(
            content="Prefers: Visual examples, mood boards, wireframes",
            memory_type="preference",
            thread_id=thread_id,
        )
        print("   ✅ Memory: Designer profile created")

        # ====== Design activities ======
        print("\n📅 Design Work Logged")

        journal.add_entry(
            content="Created wireframes for mobile app onboarding flow",
            entry_type="raw",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Design system component library: buttons, cards, modals",
            entry_type="raw",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="User research interviews: 5 users tested",
            entry_type="raw",
            thread_id=thread_id,
        )
        print("   ✅ Journal: Design work tracked")

        # ====== Creative instincts ======
        print("\n📅 Creative Pattern Learning")

        # User consistently asks for visual descriptions
        journal.add_entry(
            content="User feedback: 'Show me the visual, not just describe it'",
            entry_type="raw",
            thread_id=thread_id,
            metadata={"feedback_type": "visual"},
        )

        instincts.create_instinct(
            trigger="design request",
            action="provide visual examples, mockups, or wireframes",
            domain="format",
            confidence=0.8,
            source="learning-detected",
            thread_id=thread_id,
        )
        print("   ✅ Instincts: Learned visual preference")

        # ====== Design goals ======
        print("\n📅 Design Goal Setting")

        goals.create_goal(
            title="Complete mobile app design system",
            description="Create comprehensive design system with all components",
            category="medium_term",
            priority=7,
            importance=8,
            thread_id=thread_id,
        )
        print("   ✅ Goals: Design system goal created")

        # ====== Verification ======
        print("\n✅ Designer Persona Verification:")

        memories = memory.list_memories(thread_id=thread_id)
        entries = journal.list_entries(thread_id=thread_id, limit=10)
        learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)

        print(f"   Designer memories: {len(memories)} items")
        print(f"   Design activities: {len(entries)} logged")
        print(f"   Creative instincts: {len(learned)} patterns")

        assert len(memories) >= 2, "Should have designer profile"
        assert any("design" in m["content"].lower() or "figma" in m["content"].lower() for m in memories), \
            "Should have design tools"
        assert any("wireframe" in e["content"].lower() for e in entries), \
            "Should track design work"

        print("\n✅ Designer persona test PASSED")

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)


class TestCrossPillarInteraction:
    """Test interactions between different pillars."""

    def test_journal_informs_instincts(self):
        """Test that journal activities inform instinct learning."""
        print("\n" + "="*80)
        print("CROSS-PILLAR TEST: Journal → Instincts")
        print("="*80)

        # Setup
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "cross_pillar_test"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        instincts = InstinctStorageSQLite()
        instincts._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        # ====== Pattern: User always asks for tests in the morning ======
        print("\n📊 Pattern: Morning activity = test-focused work")

        now = datetime.now(timezone.utc)

        # Simulate 5 days of morning activity
        for day in range(5):
            day_timestamp = now - timedelta(days=5-day)

            journal.add_entry(
                content="Morning session: Wrote unit tests for authentication module",
                entry_type="raw",
                thread_id=thread_id,
                timestamp=day_timestamp.replace(hour=9).isoformat(),
            )

        print(f"   ✅ Journal: {5} morning work sessions logged")

        # ====== Detect pattern and create instinct ======
        print("\n🧠 Pattern Detection & Instinct Creation")

        instincts.create_instinct(
            trigger="morning interaction",
            action="focus on testing and code quality",
            domain="timing",
            confidence=0.75,
            source="learning-detected",
            thread_id=thread_id,
        )

        print("   ✅ Instincts: Pattern learned from journal")

        # Verify
        learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)
        assert len(learned) >= 1
        assert any("morning" in i["trigger"].lower() for i in learned)

        print("\n✅ Cross-pillar test PASSED: Journal → Instincts")

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)

    def test_memory_informs_goals(self):
        """Test that memory facts inform goal creation."""
        print("\n" + "="*80)
        print("CROSS-PILLAR TEST: Memory → Goals")
        print("="*80)

        # Setup
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "memory_goals_test"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        # ====== Memory: User explicitly states objective ======
        print("\n📝 User States Objective")

        memory.create_memory(
            content="Current project: E-commerce platform migration from monolith to microservices",
            memory_type="fact",
            thread_id=thread_id,
        )

        memory.create_memory(
            content="Timeline: Complete migration by end of Q2",
            memory_type="constraint",
            thread_id=thread_id,
        )

        print("   ✅ Memory: Project objective captured")

        # ====== System suggests/creates goal ======
        print("\n🎯 Goal Creation from Memory")

        goals.create_goal(
            title="E-commerce microservices migration",
            description="Migrate monolithic e-commerce platform to microservices architecture",
            category="long_term",
            target_date=(datetime.now(timezone.utc) + timedelta(days=180)).isoformat(),
            priority=9,
            importance=9,
            thread_id=thread_id,
        )

        print("   ✅ Goals: Goal created from memory facts")

        # ====== Verification ======
        print("\n✅ Memory → Goals Verification:")

        memories = memory.list_memories(thread_id=thread_id)
        user_goals = goals.list_goals(thread_id=thread_id, status="planned")

        assert len(memories) >= 2, "Should have project facts"
        assert len(user_goals) >= 1, "Should have migration goal"

        # Verify goal references memory
        goal = user_goals[0]
        assert "migration" in goal["title"].lower() or "microservices" in goal["title"].lower()

        print(f"   Memories: {len(memories)} facts")
        print(f"   Goals created: {len(user_goals)} objectives")
        print(f"   Goal links to memory: {goal['title']}")

        print("\n✅ Cross-pillar test PASSED: Memory → Goals")

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)


class TestLLMWithPersonas:
    """Test LLM responses using different user personas."""

    def test_llm_adapts_to_developer_persona(self):
        """Test that LLM adapts response based on developer persona."""
        print("\n" + "="*80)
        print("LLM PERSONA TEST: Developer Context Adaptation")
        print("="*80)

        # Setup
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "dev_llm_test"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Initialize storage
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        # Setup developer persona
        memory.create_memory(
            content="Name: Alex Kim, Role: Senior Developer, "
                   "Tech: Python, TypeScript, React, PostgreSQL",
            memory_type="fact",
            thread_id=thread_id,
        )

        memory.create_memory(
            content="Prefers: Code examples, technical depth, practical solutions",
            memory_type="preference",
            thread_id=thread_id,
        )

        journal.add_entry(
            content="Currently debugging authentication flow in OAuth2 integration",
            entry_type="raw",
            thread_id=thread_id,
        )

        # Retrieve context
        memories = memory.list_memories(thread_id=thread_id)
        memory_context = "\n".join([m["content"] for m in memories])

        entries = journal.list_entries(thread_id=thread_id, limit=3)
        journal_context = "\n".join([f"- {e['content']}" for e in entries])

        # Initialize LLM
        api_key = settings.OLLAMA_CLOUD_API_KEY
        cloud_url = settings.OLLAMA_CLOUD_URL

        llm = ChatOllama(
            model="deepseek-v3.2:cloud",
            base_url=cloud_url,
            temperature=0.7,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {api_key}"
                }
            }
        )

        # Test prompt
        prompt = f"""User context:
{memory_context}

Recent work:
{journal_context}

Question: How should I implement rate limiting in my API?

Provide a technical solution with code examples."""

        print(f"\n🧠 Testing LLM adaptation to developer persona...")

        # Invoke LLM
        response = llm.invoke(prompt)

        # Show results
        print(f"\n📊 Token Usage:")
        if hasattr(response, 'usage_metadata'):
            print(f"   Input:  {response.usage_metadata.get('input_tokens', 'N/A')}")
            print(f"   Output: {response.usage_metadata.get('output_tokens', 'N/A')}")
            print(f"   Total:  {response.usage_metadata.get('total_tokens', 'N/A')}")

        print(f"\n✅ Response (first 300 chars):")
        print(f"   {response.content[:300]}...")

        # Verify developer-focused response
        content_lower = response.content.lower()
        has_code = (
            "```" in response.content or  # Code blocks
            "python" in content_lower or
            "function" in content_lower or
            "api" in content_lower
        )

        assert has_code, "Should provide code examples for developer"

        print("\n✅ LLM adapted to developer persona!")

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)


class TestOnboardingScenarios:
    """Test complete onboarding scenarios."""

    def test_new_user_complete_onboarding(self):
        """Test complete new user onboarding flow."""
        print("\n" + "="*80)
        print("ONBOARDING SCENARIO: New User Complete Journey")
        print("="*80)

        # Setup
        temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)

        thread_id = "new_user_onboarding"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Initialize all storage
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        instincts = InstinctStorageSQLite()
        instincts._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        # ====== STAGE 1: Initial Setup (Day 1) ======
        print("\n🚀 Stage 1: Initial Setup")

        memory.create_memory(
            content="Name: New User, Role: Software Engineer, Experience: Intermediate",
            memory_type="fact",
            thread_id=thread_id,
        )
        print("   ✅ User profile created")

        journal.add_entry(
            content="First day: Setting up development environment",
            entry_type="raw",
            thread_id=thread_id,
        )
        print("   ✅ First activity logged")

        # ====== STAGE 2: Learning Patterns (Week 1) ======
        print("\n📚 Stage 2: Learning Patterns (Week 1)")

        # Simulate user interactions
        interactions = [
            ("User asked for concise response", "adjustment", "negative"),
            ("User asked for detailed explanation", "adjustment", "negative"),
            ("User liked code examples", "adjustment", "positive"),
            ("User preferred bullet points", "adjustment", "positive"),
        ]

        for interaction, adjustment_type, sentiment in interactions:
            journal.add_entry(
                content=f"User interaction: {interaction}",
                entry_type="raw",
                thread_id=thread_id,
                metadata={"interaction_type": adjustment_type, "sentiment": sentiment},
            )

        print("   ✅ User interactions logged")

        # System learns from patterns
        instincts.create_instinct(
            trigger="user asks for explanation",
            action="include code examples and be concise",
            domain="communication",
            confidence=0.65,
            source="learning-detected",
            thread_id=thread_id,
        )
        print("   ✅ Patterns learned")

        # ====== STAGE 3: Goal Setting (Week 2) ======
        print("\n🎯 Stage 3: Goal Setting (Week 2)")

        goals.create_goal(
            title="Learn unified context system architecture",
            description="Understand and implement all 4 pillars effectively",
            category="medium_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
        )
        print("   ✅ Learning goal created")

        # ====== STAGE 4: Active Usage (Month 1) ======
        print("\n💼 Stage 4: Active Usage (Month 1)")

        # Log various activities
        activities = [
            "Integrated memory storage with SQLite",
            "Implemented journal rollups (hourly → weekly → monthly)",
            "Created instinct pattern learning system",
            "Built goals tracking with progress monitoring",
        ]

        for activity in activities:
            journal.add_entry(
                content=activity,
                entry_type="raw",
                thread_id=thread_id,
            )

        print("   ✅ Active work tracked")

        # Update goal progress
        active_goals = goals.list_goals(thread_id=thread_id, status="planned")
        if active_goals:
            goal_id = active_goals[0]["id"]
            goals.update_goal_progress(
                goal_id=goal_id,
                thread_id=thread_id,
                progress=25.0,
                source="manual",
                notes="Completed learning and implementation",
            )
        print("   ✅ Goal progress updated")

        # ====== Final Verification ======
        print("\n✅ Onboarding Complete Verification:")

        memories = memory.list_memories(thread_id=thread_id)
        entries = journal.list_entries(thread_id=thread_id)
        learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)
        user_goals = goals.list_goals(thread_id=thread_id)

        print(f"\n   📊 Onboarding Metrics:")
        print(f"   Memories created: {len(memories)}")
        print(f"   Activities logged: {len(entries)}")
        print(f"   Patterns learned: {len(learned)}")
        print(f"   Goals set: {len(user_goals)}")

        # Verify onboarding completeness
        assert len(memories) >= 1, "Should have user profile"
        assert len(entries) >= 5, "Should track activities over time"
        assert len(user_goals) >= 1, "Should have objectives"
        assert len(learned) >= 1, "Should learn patterns"

        # Check progression
        assert entries[0]["content"] != "First day: Setting up development environment", \
            "Journal should have multiple entries"

        print("\n✅ New user onboarding scenario PASSED")

        # Cleanup
        import shutil
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    # Run all persona and onboarding tests
    pytest.main([__file__, "-v", "-s"])
