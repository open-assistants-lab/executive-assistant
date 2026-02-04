#!/usr/bin/env python3
"""
Context Retention Tests - MINIMAL TOKEN VERSION

Tests: 3 messages per model
- Test: Remember info after 3 exchanges

Estimated token usage: ~8K-15K tokens per model
"""

import subprocess
import time
import json
import os

def start_agent(provider, model, user_id):
    """Start agent with specified model"""
    subprocess.run(["pkill", "-f", "executive_assistant"], stderr=subprocess.DEVNULL)
    time.sleep(2)

    user_folder = f"data/users/http_http_{user_id}"
    if os.path.exists(user_folder):
        subprocess.run(["rm", "-rf", user_folder])

    env = os.environ.copy()
    env["DEFAULT_LLM_PROVIDER"] = provider
    if provider == "openai":
        env["OPENAI_MODEL"] = model
    elif provider == "anthropic":
        env["ANTHROPIC_MODEL"] = model
    elif provider == "ollama":
        env["OLLAMA_DEFAULT_MODEL"] = model

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

def test_context_retention(provider, model, user_id):
    """Test context retention over 3 messages"""
    print(f"\n{'='*60}")
    print(f"MODEL: {model} ({provider})")
    print(f"{'='*60}")

    start_agent(provider, model, user_id)

    # Message 1: Establish context
    print("\n[Message 1] Establish context")
    print("-" * 60)
    msg1 = "I'm analyzing Q4 sales data from PostgreSQL"
    print(f"User: {msg1}")
    resp1 = send_message(user_id, msg1)
    print(f"Agent: {resp1[:150]}...")
    time.sleep(1)

    # Message 2: Add more context
    print("\n[Message 2] Add context")
    print("-" * 60)
    msg2 = "The database is at localhost:5432"
    print(f"User: {msg2}")
    resp2 = send_message(user_id, msg2)
    print(f"Agent: {resp2[:150]}...")
    time.sleep(1)

    # Message 3: Test retention (should remember Q4, PostgreSQL, localhost)
    print("\n[Message 3] Test retention")
    print("-" * 60)
    msg3 = "Create a table to store the analysis results"
    print(f"User: {msg3}")
    resp3 = send_message(user_id, msg3)
    print(f"Agent: {resp3[:200]}...")

    # Check if agent remembered context
    has_q4 = "q4" in resp3.lower()
    has_postgres = "postgres" in resp3.lower() or "sql" in resp3.lower()
    has_analysis = "analysis" in resp3.lower() or "sales" in resp3.lower()

    print(f"\nContext Retention Check:")
    print(f"  ✓ Remembers 'Q4': {has_q4}")
    print(f"  ✓ Remembers 'PostgreSQL': {has_postgres}")
    print(f"  ✓ Remembers 'sales analysis': {has_analysis}")

    score = sum([has_q4, has_postgres, has_analysis])
    print(f"\nScore: {score}/3")

    return score == 3

def test_model(provider, model):
    """Run context retention test"""
    user_id = f"{provider}_{model.replace(':', '_').replace('-', '_')}_context"
    passed = test_context_retention(provider, model, user_id)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {model}")
    print(f"{'='*60}")
    print(f"Context Retention: {'✅ PASS' if passed else '❌ FAIL'}")

    return passed

if __name__ == "__main__":
    # Test TOP 4 models (3 msgs × 4 models = 12 messages total)
    models = [
        ("ollama", "deepseek-v3.2:cloud"),           # Best free
        ("anthropic", "claude-sonnet-4-5-20250929"),  # Best paid
        ("ollama", "qwen3-next:80b-cloud"),           # Efficient
        ("openai", "gpt-5.2-2025-12-11"),            # OpenAI
    ]

    print("="*60)
    print("CONTEXT RETENTION TESTS - Top 4 Models")
    print("Estimated: 12 messages total (~20K tokens)")
    print("="*60)

    results = {}
    for provider, model in models:
        results[model] = test_model(provider, model)

    # Final summary
    print("\n" + "="*60)
    print("FINAL RESULTS - Context Retention")
    print("="*60)
    for model, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{model}: {status}")
