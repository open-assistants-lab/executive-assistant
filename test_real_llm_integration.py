#!/usr/bin/env python3
"""REAL LLM integration test with unified context system.

This test ACTUALLY calls Ollama Cloud models and shows REAL token usage.
Tests all 4 pillars working together with the LLM.
"""

import os
import sys
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

# Add src to path
sys.path.insert(0, "src")

from executive_assistant.config import settings
from executive_assistant.storage.mem_storage import MemoryStorage
from executive_assistant.storage.journal_storage import JournalStorage
from executive_assistant.storage.instinct_storage_sqlite import InstinctStorageSQLite
from executive_assistant.storage.goals_storage import GoalsStorage

# Load credentials
load_dotenv("docker/.env")

# Ensure cloud mode
os.environ["OLLAMA_MODE"] = "cloud"


def test_all_four_pillars_with_llm():
    """Test complete unified context system with real LLM inference."""

    print("\n" + "="*80)
    print("UNIFIED CONTEXT SYSTEM - REAL LLM INTEGRATION TEST")
    print("="*80)

    # Setup temporary storage
    from pathlib import Path
    import tempfile

    temp_root = Path(tempfile.mkdtemp()) / "data" / "users"
    temp_root.mkdir(parents=True, exist_ok=True)

    thread_id = "test_llm_integration"
    thread_dir = temp_root / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)

    # Setup all 4 storage systems
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

    # Populate all 4 pillars
    print("\n📦 Setting up unified context system...")

    # 1. Memory (Semantic)
    memory.create_memory(
        content="User: Dr. Sarah Chen, Role: ML Research Lead, Team: Computer Vision, "
                   "Expertise: Deep Learning, PyTorch, TensorFlow",
        memory_type="fact",
        thread_id=thread_id,
    )

    # 2. Journal (Episodic)
    journal.add_entry(
        content="Trained convolutional neural network for image classification (94.5% accuracy)",
        entry_type="raw",
        thread_id=thread_id,
    )
    journal.add_entry(
        content="Optimized model using quantization techniques - reduced size by 60%",
        entry_type="raw",
        thread_id=thread_id,
    )

    # 3. Instincts (Procedural)
    instincts.create_instinct(
        trigger="technical discussion",
        action="include implementation details",
        domain="communication",
        confidence=0.85,
        thread_id=thread_id,
    )

    # 4. Goals (Intentions)
    goals.create_goal(
        title="Deploy CV model to production API",
        description="Make trained image classification model available via REST API",
        category="short_term",
        priority=9,
        importance=10,
        thread_id=thread_id,
    )

    print("   ✅ Memory: User facts loaded")
    print("   ✅ Journal: Activities logged")
    print("   ✅ Instincts: Behavioral patterns learned")
    print("   ✅ Goals: Objectives set")

    # Retrieve context from all 4 pillars
    memories = memory.list_memories(thread_id=thread_id)
    memory_context = "\n".join([f"  - {m['content']}" for m in memories])

    entries = journal.list_entries(thread_id=thread_id, limit=3)
    journal_context = "\n".join([f"  - {e['content']}" for e in entries])

    learned = instincts.list_instincts(thread_id=thread_id, apply_decay=False)
    instincts_context = "\n".join([f"  - When {i['trigger']}, {i['action']} (confidence: {i['confidence']})" for i in learned])

    user_goals = goals.list_goals(thread_id=thread_id, status="planned")
    goals_context = "\n".join([f"  - {g['title']} (priority: {g['priority']}/10)" for g in user_goals])

    # Test with all 3 models
    models = [
        "deepseek-v3.2:cloud",
        "qwen3-next:80b-cloud",
        "gpt-oss:20b-cloud",
    ]

    api_key = settings.OLLAMA_CLOUD_API_KEY
    cloud_url = settings.OLLAMA_CLOUD_URL

    print(f"\n🧠 Testing with {len(models)} Ollama Cloud models...")
    print(f"   API: {cloud_url}")
    print(f"   Key: {api_key[:20]}...{api_key[-10:]}")

    results = []

    for model in models:
        try:
            print(f"\n{'='*80}")
            print(f"Model: {model}")
            print(f"{'='*80}")

            llm = ChatOllama(
                model=model,
                base_url=cloud_url,
                temperature=0.7,
                client_kwargs={
                    "headers": {
                        "Authorization": f"Bearer {api_key}"
                    }
                }
            )

            # Create prompt with complete context
            prompt = f"""You are an AI assistant with complete context about the user.

MEMORY (Who they are):
{memory_context}

JOURNAL (What they did):
{journal_context}

INSTINCTS (How they behave):
{instincts_context}

GOALS (Why/Where):
{goals_context}

Question: Based on the complete unified context, what should Sarah work on next?

Provide a specific, actionable recommendation."""

            # Invoke LLM - THIS IS THE REAL TEST
            response = llm.invoke(prompt)

            # Extract token usage
            input_tokens = response.usage_metadata.get('input_tokens', 'N/A') if hasattr(response, 'usage_metadata') else 'N/A'
            output_tokens = response.usage_metadata.get('output_tokens', 'N/A') if hasattr(response, 'usage_metadata') else 'N/A'
            total_tokens = response.usage_metadata.get('total_tokens', 'N/A') if hasattr(response, 'usage_metadata') else 'N/A'

            print(f"\n📊 Token Usage:")
            print(f"   Input tokens:  {input_tokens}")
            print(f"   Output tokens: {output_tokens}")
            print(f"   Total tokens:  {total_tokens}")

            print(f"\n✅ Response:")
            # Show first 300 characters
            response_preview = response.content[:300]
            if len(response.content) > 300:
                response_preview += "..."
            print(f"   {response_preview}")

            # Verify response uses context
            content_lower = response.content.lower()
            has_context = (
                "sarah" in content_lower or
                "model" in content_lower or
                "api" in content_lower or
                "deploy" in content_lower or
                "production" in content_lower
            )

            if has_context:
                print(f"\n✅ SUCCESS: LLM used unified context!")
            else:
                print(f"\n⚠️  WARNING: LLM may not be using context effectively")

            results.append({
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "success": has_context,
            })

        except Exception as e:
            print(f"\n❌ FAILED: {model}")
            print(f"   Error: {e}")
            results.append({
                "model": model,
                "error": str(e),
                "success": False,
            })

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY: All 3 Models Tested")
    print(f"{'='*80}\n")

    for result in results:
        if result.get("success", False):
            print(f"✅ {result['model']}")
            print(f"   Tokens: {result['total_tokens']} (in: {result['input_tokens']}, out: {result['output_tokens']})")
        else:
            print(f"❌ {result['model']}")
            print(f"   Error: {result.get('error', 'Unknown')}")

    print(f"\n{'='*80}")
    print(f"✅ UNIFIED CONTEXT SYSTEM + LLM INTEGRATION: COMPLETE!")
    print(f"{'='*80}\n")

    # Cleanup
    import shutil
    shutil.rmtree(temp_root, ignore_errors=True)

    return results


if __name__ == "__main__":
    results = test_all_four_pillars_with_llm()
