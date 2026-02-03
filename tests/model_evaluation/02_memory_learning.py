#!/usr/bin/env python3
"""
Memory & Learning Tests - MINIMAL TOKEN VERSION

Tests: 2 messages per model
- Test A: Memory Creation (1 message)
- Test B: Memory Retrieval (1 message in new conversation)

Estimated token usage: ~5K-10K tokens per model (well under 1M limit)
"""

import subprocess
import time
import json
import sqlite3
import os
from pathlib import Path

def start_agent(provider, model, user_id):
    """Start agent with specified model"""
    # Kill existing
    subprocess.run(["pkill", "-f", "executive_assistant"], stderr=subprocess.DEVNULL)
    time.sleep(2)

    # Clean user data (folder format is http_http_{user_id})
    user_folder = f"data/users/http_http_{user_id}"
    if os.path.exists(user_folder):
        subprocess.run(["rm", "-rf", user_folder])

    # Set environment
    env = os.environ.copy()
    env["DEFAULT_LLM_PROVIDER"] = provider
    if provider == "openai":
        env["OPENAI_MODEL"] = model
    elif provider == "anthropic":
        env["ANTHROPIC_MODEL"] = model
    elif provider == "ollama":
        env["OLLAMA_DEFAULT_MODEL"] = model

    # Start agent
    log_file = f"/tmp/agent_{user_id}.log"
    with open(log_file, "w") as log:
        subprocess.Popen(
            ["uv", "run", "executive_assistant"],
            env=env,
            stdout=log,
            stderr=log,
            cwd="/Users/eddy/Developer/Langgraph/ken"
        )

    time.sleep(12)
    return log_file

def send_message(user_id, content):
    """Send message to agent"""
    result = subprocess.run([
        "curl", "-s", "-X", "POST", "http://localhost:8000/message",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"content": content, "user_id": user_id, "stream": False})
    ], capture_output=True, text=True)

    try:
        response = json.loads(result.stdout)
        if isinstance(response, list):
            return response[0].get("content", "")
        return response.get("content", "")
    except:
        return result.stdout

def check_memories(user_id):
    """Check what memories were stored"""
    # The actual folder format is http_http_{user_id}
    mem_db = f"data/users/http_http_{user_id}/mem/mem.db"
    if not os.path.exists(mem_db):
        return []

    try:
        conn = sqlite3.connect(mem_db)
        cursor = conn.cursor()
        cursor.execute("SELECT key, content, memory_type FROM memories WHERE memory_type IN ('profile', 'fact', 'preference')")
        memories = cursor.fetchall()
        conn.close()
        return [{"key": m[0], "content": m[1], "type": m[2]} for m in memories]
    except Exception as e:
        return [{"error": str(e)}]

def test_memory_creation(provider, model, user_id):
    """Test A: Create memories via onboarding"""
    print(f"\n{'='*60}")
    print(f"MODEL: {model} ({provider})")
    print(f"{'='*60}")
    print("\n[Test A] Memory Creation (via Onboarding)")
    print("-" * 60)

    start_agent(provider, model, user_id)

    # Message 1: Trigger onboarding
    msg1 = "hi"
    print(f"User: {msg1}")
    resp1 = send_message(user_id, msg1)
    print(f"Agent: {resp1[:150]}...")
    time.sleep(1)

    # Message 2: Provide user info (during onboarding)
    msg2 = "My name is Alice, I'm a product manager at Acme Corp"
    print(f"\nUser: {msg2}")
    resp2 = send_message(user_id, msg2)
    print(f"Agent: {resp2[:150]}...")

    # Check memories
    memories = check_memories(user_id)
    print(f"\nMemories stored: {len(memories)}")
    for m in memories:
        print(f"  - [{m.get('type', 'unknown')}] {m.get('key', 'N/A')}: {m.get('content', 'N/A')[:80]}")

    return len(memories) > 0

def test_memory_retrieval(provider, model, user_id):
    """Test B: Retrieve memories in new conversation"""
    print(f"\n[Test B] Memory Retrieval (New Conversation)")
    print("-" * 60)

    # Restart agent (simulates new conversation)
    start_agent(provider, model, user_id)

    # Ask what agent remembers
    message = "What do you remember about me?"
    print(f"User: {message}")
    response = send_message(user_id, message)
    print(f"Agent: {response[:300]}...")

    # Check if response contains key info
    has_name = "alice" in response.lower()
    has_role = "product manager" in response.lower() or "pm" in response.lower()
    has_company = "acme" in response.lower()

    print(f"\nRetrieval Check:")
    print(f"  ✓ Name (Alice): {has_name}")
    print(f"  ✓ Role (PM): {has_role}")
    print(f"  ✓ Company (Acme): {has_company}")

    return has_name and has_role and has_company

def test_model(provider, model):
    """Run both memory tests for a model"""
    base_id = f"{provider}_{model.replace(':', '_').replace('-', '_')}"

    # Test A: Creation
    created = test_memory_creation(provider, model, base_id)

    # Test B: Retrieval (use different user_id for clean state)
    retrieved = test_memory_retrieval(provider, model, base_id + "_retrieval")

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: {model}")
    print(f"{'='*60}")
    print(f"Memory Creation: {'✅ PASS' if created else '❌ FAIL'}")
    print(f"Memory Retrieval: {'✅ PASS' if retrieved else '❌ FAIL'}")
    print(f"Overall: {'✅ PASS' if (created and retrieved) else '❌ FAIL'}")

    return {"created": created, "retrieved": retrieved}

if __name__ == "__main__":
    # Test TOP 3 models (4 msgs per model = 12 messages total)
    # - 2 messages for creation (hi + user info)
    # - 2 messages for retrieval (new conversation)
    models = [
        ("ollama", "deepseek-v3.2:cloud"),           # Best free
        ("anthropic", "claude-sonnet-4-5-20250929"),  # Best paid
        ("ollama", "qwen3-next:80b-cloud"),           # Most efficient
    ]

    print("="*60)
    print("MEMORY & LEARNING TESTS - Top 3 Models")
    print("Estimated: 12 messages total (~20K tokens)")
    print("="*60)

    results = {}
    for provider, model in models:
        results[model] = test_model(provider, model)

    # Final summary
    print("\n" + "="*60)
    print("FINAL RESULTS - Memory & Learning")
    print("="*60)
    for model, result in results.items():
        status = "✅ PASS" if (result["created"] and result["retrieved"]) else "❌ FAIL"
        print(f"{model}: {status}")
