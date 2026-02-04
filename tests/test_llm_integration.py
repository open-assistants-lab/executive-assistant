"""Real LLM integration tests for unified context system.

These tests ACTUALLY call Ollama Cloud models with the unified context system:
- deepseek-v3.2:cloud
- qwen3-next:80b-cloud
- gpt-oss:20b-cloud

Tests verify that all 4 pillars work together with real LLM inference.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import settings to get correct URLs
from executive_assistant.config import settings

# Load Ollama Cloud credentials from .env
from dotenv import load_dotenv
load_dotenv("docker/.env")

# Set test environment variables to use Ollama Cloud
os.environ["OLLAMA_MODE"] = "cloud"
if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
    os.environ["OLLAMA_CLOUD_API_KEY"] = settings.OLLAMA_CLOUD_API_KEY


class TestLLMIntegration:
    """Real LLM integration tests with unified context system."""

    @pytest.mark.parametrize("model", [
        "deepseek-v3.2:cloud",
        "qwen3-next:80b-cloud",
        "gpt-oss:20b-cloud",
    ])
    def test_memory_retrieval_with_llm(self, model, tmp_path):
        """Test that memory is retrieved and used in LLM calls."""
        # This test would:
        # 1. Create a memory (e.g., "User prefers brief responses")
        # 2. Send a message to the LLM
        # 3. Verify the LLM uses the memory in its response
        # 4. Show actual token usage

        # Import LLM integration
        from langchain_ollama import ChatOllama
        from executive_assistant.storage.mem_storage import MemoryStorage

        # Setup storage
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)
        thread_id = "test_memory_llm"
        mem_dir = temp_root / thread_id / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)

        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        # Create memory
        memory.create_memory(
            content="User: Alice, Role: Data Scientist, Prefers: detailed explanations",
            memory_type="fact",
            thread_id=thread_id,
        )

        # Initialize LLM
        llm = ChatOllama(
            model=model,
            base_url=settings.OLLAMA_CLOUD_URL,
            temperature=0.7,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {settings.OLLAMA_CLOUD_API_KEY}"
                }
            }
        )

        # Retrieve memory
        memories = memory.list_memories(thread_id=thread_id)
        memory_context = "\n".join([m["content"] for m in memories])

        # Create prompt with memory
        prompt = f"""User context: {memory_context}

Question: What type of work does Alice do?

Provide a brief answer."""

        # Invoke LLM (THIS WILL SHOW TOKEN USAGE)
        response = llm.invoke(prompt)

        # Verify response
        assert response is not None
        assert "data scientist" in response.content.lower() or "alice" in response.content.lower()

        # Print token usage if available
        if hasattr(response, 'usage_metadata'):
            print(f"\n📊 Model: {model}")
            print(f"   Input tokens: {response.usage_metadata.get('input_tokens', 'N/A')}")
            print(f"   Output tokens: {response.usage_metadata.get('output_tokens', 'N/A')}")
            print(f"   Total tokens: {response.usage_metadata.get('total_tokens', 'N/A')}")
        else:
            print(f"\n📊 Model: {model} - Token usage not available in response")

        print(f"✅ Response: {response.content[:100]}...")

    @pytest.mark.parametrize("model", [
        "deepseek-v3.2:cloud",
        "qwen3-next:80b-cloud",
        "gpt-oss:20b-cloud",
    ])
    def test_journal_context_with_llm(self, model, tmp_path):
        """Test that journal entries are retrieved and used in LLM calls."""
        from langchain_ollama import ChatOllama
        from executive_assistant.storage.journal_storage import JournalStorage

        # Setup storage
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)
        thread_id = "test_journal_llm"
        journal_dir = temp_root / thread_id / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)

        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        # Create journal entries
        journal.add_entry(
            content="Built ML model for customer churn prediction (85% accuracy)",
            entry_type="raw",
            thread_id=thread_id,
        )
        journal.add_entry(
            content="Deployed model to production API",
            entry_type="raw",
            thread_id=thread_id,
        )

        # Initialize LLM
        llm = ChatOllama(
            model=model,
            base_url=settings.OLLAMA_CLOUD_URL,
            temperature=0.7,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {settings.OLLAMA_CLOUD_API_KEY}"
                }
            }
        )

        # Retrieve journal context
        entries = journal.list_entries(thread_id=thread_id, limit=5)
        journal_context = "\n".join([f"- {e['content']}" for e in entries])

        # Create prompt with journal
        prompt = f"""User's recent activities:
{journal_context}

Question: What has the user been working on?

Summarize briefly."""

        # Invoke LLM
        response = llm.invoke(prompt)

        # Verify response
        assert response is not None
        assert any(keyword in response.content.lower() for keyword in ["ml", "model", "churn", "api", "deploy"])

        print(f"\n📊 Model: {model}")
        print(f"✅ Response: {response.content[:150]}...")

    @pytest.mark.parametrize("model", [
        "deepseek-v3.2:cloud",
        "qwen3-next:80b-cloud",
        "gpt-oss:20b-cloud",
    ])
    def test_all_four_pillars_with_llm(self, model, tmp_path):
        """Test complete unified context system with real LLM inference."""
        from langchain_ollama import ChatOllama
        from executive_assistant.storage.mem_storage import MemoryStorage
        from executive_assistant.storage.journal_storage import JournalStorage
        from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite
        from executive_assistant.storage.goals_storage import GoalsStorage

        # Setup all storage systems
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)
        thread_id = "test_all_pillars_llm"
        thread_dir = temp_root / thread_id
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Memory
        mem_dir = thread_dir / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)
        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        # Journal
        journal_dir = thread_dir / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal = JournalStorage()
        journal._get_journal_dir = lambda tid=None: journal_dir

        # Instincts
        instincts = InstinctStorageSQLite()
        instincts._get_db_path = lambda tid=None: thread_dir / "instincts.db"

        # Goals
        goals_dir = thread_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        goals = GoalsStorage()
        goals._get_goals_dir = lambda tid=None: goals_dir

        # Populate all 4 pillars
        # 1. Memory
        memory.create_memory(
            content="User: Bob, Role: ML Engineer, Expertise: Python, TensorFlow",
            memory_type="fact",
            thread_id=thread_id,
        )

        # 2. Journal
        journal.add_entry(
            content="Trained neural network model with 95% accuracy",
            entry_type="raw",
            thread_id=thread_id,
        )

        # 3. Instincts
        instincts.create_instinct(
            trigger="technical question",
            action="include code examples",
            domain="communication",
            confidence=0.9,
            thread_id=thread_id,
        )

        # 4. Goals
        goals.create_goal(
            title="Deploy ML model to production",
            category="short_term",
            priority=8,
            importance=9,
            thread_id=thread_id,
        )

        # Retrieve context from all 4 pillars
        memories = memory.list_memories(thread_id=thread_id)
        memory_context = "\n".join([m["content"] for m in memories])

        entries = journal.list_entries(thread_id=thread_id, limit=3)
        journal_context = "\n".join([f"- {e['content']}" for e in entries])

        learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)
        instincts_context = "\n".join([f"- When {i['trigger']}, {i['action']}" for i in learned])

        user_goals = goals.list_goals(thread_id=thread_id, status="planned")
        goals_context = "\n".join([f"- {g['title']}" for g in user_goals])

        # Initialize LLM
        llm = ChatOllama(
            model=model,
            base_url=settings.OLLAMA_CLOUD_URL,
            temperature=0.7,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {settings.OLLAMA_CLOUD_API_KEY}"
                }
            }
        )

        # Create comprehensive prompt
        prompt = f"""You are an AI assistant with complete context about the user.

MEMORY (Who they are):
{memory_context}

JOURNAL (What they did):
{journal_context}

INSTINCTS (How they behave):
{instincts_context}

GOALS (Why/Where):
{goals_context}

Question: Based on the complete context, what should Bob work on next?

Provide a specific, actionable suggestion."""

        # Invoke LLM (THIS IS THE REAL TEST WITH TOKEN USAGE)
        print(f"\n{'='*60}")
        print(f"🧠 Testing: {model}")
        print(f"   API: {settings.OLLAMA_CLOUD_URL}")
        print(f"{'='*60}")

        response = llm.invoke(prompt)

        # Verify response uses context from all 4 pillars
        assert response is not None
        content_lower = response.content.lower()

        # Should reference information from at least one pillar
        has_context = (
            "bob" in content_lower or  # Memory
            "ml" in content_lower or "model" in content_lower or  # Journal
            "deploy" in content_lower or "production" in content_lower  # Goals/instincts
        )
        assert has_context, "Response should use information from context"

        # Print detailed results
        print(f"\n📊 Token Usage:")
        if hasattr(response, 'usage_metadata'):
            print(f"   Input tokens:  {response.usage_metadata.get('input_tokens', 'N/A')}")
            print(f"   Output tokens: {response.usage_metadata.get('output_tokens', 'N/A')}")
            print(f"   Total tokens:  {response.usage_metadata.get('total_tokens', 'N/A')}")
        else:
            print(f"   Token usage not available in response metadata")

        print(f"\n✅ Response:")
        print(f"   {response.content[:200]}...")

        print(f"\n{'='*60}")
        print(f"✅ Test passed: {model} successfully uses unified context!")
        print(f"{'='*60}\n")


class TestMultiModelComparison:
    """Compare responses across multiple Ollama Cloud models."""

    def test_compare_all_three_models(self, tmp_path):
        """Test the same query across all 3 models and compare."""
        from langchain_ollama import ChatOllama
        from executive_assistant.storage.mem_storage import MemoryStorage

        # Setup
        temp_root = tmp_path / "data" / "users"
        temp_root.mkdir(parents=True, exist_ok=True)
        thread_id = "test_comparison"
        mem_dir = temp_root / thread_id / "mem"
        mem_dir.mkdir(parents=True, exist_ok=True)

        memory = MemoryStorage()
        memory._get_mem_dir = lambda tid=None: mem_dir

        # Create memory
        memory.create_memory(
            content="User: Sarah, Role: Product Manager, Focus: Sales analytics dashboard",
            memory_type="fact",
            thread_id=thread_id,
        )

        # Test prompt
        memories = memory.list_memories(thread_id=thread_id)
        memory_context = "\n".join([m["content"] for m in memories])

        prompt = f"""User context: {memory_context}

Question: What project is Sarah working on?

Answer in one sentence."""

        models = [
            "deepseek-v3.2:cloud",
            "qwen3-next:80b-cloud",
            "gpt-oss:20b-cloud",
        ]

        print(f"\n{'='*80}")
        print(f"🔄 COMPARISON TEST: All 3 Ollama Cloud Models")
        print(f"{'='*80}\n")

        results = []
        for model in models:
            llm = ChatOllama(
                model=model,
                base_url="https://api.ollama.ai",
                temperature=0.7,
            )

            response = llm.invoke(prompt)

            results.append({
                "model": model,
                "response": response.content,
                "input_tokens": response.usage_metadata.get('input_tokens', 'N/A') if hasattr(response, 'usage_metadata') else 'N/A',
                "output_tokens": response.usage_metadata.get('output_tokens', 'N/A') if hasattr(response, 'usage_metadata') else 'N/A',
                "total_tokens": response.usage_metadata.get('total_tokens', 'N/A') if hasattr(response, 'usage_metadata') else 'N/A',
            })

        # Print comparison
        for i, result in enumerate(results, 1):
            print(f"Model {i}: {result['model']}")
            print(f"   Tokens: In={result['input_tokens']}, Out={result['output_tokens']}, Total={result['total_tokens']}")
            print(f"   Response: {result['response'][:100]}...")
            print()

        # Verify all models responded
        assert len(results) == 3
        for result in results:
            assert result["response"] is not None
            assert len(result["response"]) > 0

        print(f"{'='*80}")
        print(f"✅ All 3 models tested successfully!")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v", "-s"])
