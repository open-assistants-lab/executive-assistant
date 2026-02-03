#!/usr/bin/env python3
"""
Error Recovery Tests - MINIMAL TOKEN VERSION

Tests: 2 messages per model
- Test A: Ambiguous request handling
- Test B: User correction handling

Estimated token usage: ~5K-10K tokens per model
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
            # Return full list for tool_use responses
            return response
        return response.get("content", "")
    except:
        return result.stdout

def test_ambiguous_request(provider, model, user_id):
    """Test A: Handle ambiguous request"""
    print(f"\n{'='*60}")
    print(f"MODEL: {model} ({provider})")
    print(f"{'='*60}")
    print("\n[Test A] Ambiguous Request Handling")
    print("-" * 60)

    start_agent(provider, model, user_id)

    # Send ambiguous request
    message = "Create a report"
    print(f"User: {message}")
    response = send_message(user_id, message)

    # Handle list responses
    if isinstance(response, list):
        response_str = json.dumps(response)
    else:
        response_str = response

    print(f"Agent: {response_str[:300]}...")

    # Check if agent asked clarifying questions
    has_question = "?" in response_str
    has_what = "what" in response_str.lower()
    has_which = "which" in response_str.lower() or "what kind" in response_str.lower()
    has_clarification = "clarif" in response_str.lower() or "more detail" in response_str.lower() or "specif" in response_str.lower()

    asked_questions = has_question or has_what or has_which or has_clarification

    print(f"\nClarification Check:")
    print(f"  ✓ Has question mark: {has_question}")
    print(f"  ✓ Asks 'what': {has_what}")
    print(f"  ✓ Asks 'which': {has_which}")
    print(f"  ✓ Asks for clarification: {has_clarification}")

    print(f"\nResult: {'✅ PASS (asked clarifying question)' if asked_questions else '⚠️  WARNING (guessed instead of asking)'}")

    return asked_questions

def test_user_correction(provider, model, user_id):
    """Test B: Handle user correction"""
    print(f"\n[Test B] User Correction Handling")
    print("-" * 60)

    # Continue from previous conversation
    message = "Create a work logs table"
    print(f"User: {message}")
    response = send_message(user_id, message)
    print(f"Agent: {response[:150]}...")
    time.sleep(1)

    # User corrects themselves
    correction = "Wait, I meant customers table, not work logs"
    print(f"\nUser: {correction}")
    response2 = send_message(user_id, correction)

    # Handle list responses (tool_use)
    if isinstance(response2, list):
        response2_str = json.dumps(response2)
    else:
        response2_str = response2

    print(f"Agent: {response2_str[:200]}...")

    # Check if agent acknowledged correction
    has_customers = "customer" in response2_str.lower()
    has_correction = "correct" in response2_str.lower() or "understood" in response2_str.lower() or "got it" in response2_str.lower() or "sorry" in response2_str.lower()
    adapted = has_customers and ("work log" not in response2_str.lower() or response2_str.lower().count("customer") > response2_str.lower().count("work log"))

    print(f"\nAdaptation Check:")
    print(f"  ✓ Created customers table: {has_customers}")
    print(f"  ✓ Acknowledged correction: {has_correction}")
    print(f"  ✓ Adapted to correction: {adapted}")

    print(f"\nResult: {'✅ PASS (adapted gracefully)' if adapted else '⚠️  PARTIAL'}")

    return adapted

def test_model(provider, model):
    """Run error recovery tests"""
    user_id = f"{provider}_{model.replace(':', '_').replace('-', '_')}_error"

    test_a = test_ambiguous_request(provider, model, user_id)
    test_b = test_user_correction(provider, model, user_id)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {model}")
    print(f"{'='*60}")
    print(f"Ambiguous Request: {'✅ PASS' if test_a else '⚠️  WARN'}")
    print(f"User Correction: {'✅ PASS' if test_b else '⚠️  WARN'}")
    print(f"Overall: {'✅ GOOD' if (test_a or test_b) else '⚠️  NEEDS IMPROVEMENT'}")

    return {"ambiguous": test_a, "correction": test_b}

if __name__ == "__main__":
    # Test TOP 4 models (2 msgs × 4 models = 8 messages total)
    models = [
        ("ollama", "deepseek-v3.2:cloud"),           # Best free
        ("anthropic", "claude-sonnet-4-5-20250929"),  # Best paid
        ("openai", "gpt-5.2-2025-12-11"),            # OpenAI
        ("ollama", "qwen3-next:80b-cloud"),           # Efficient
    ]

    print("="*60)
    print("ERROR RECOVERY TESTS - Top 4 Models")
    print("Estimated: 8 messages total (~15K tokens)")
    print("="*60)

    results = {}
    for provider, model in models:
        results[model] = test_model(provider, model)

    # Final summary
    print("\n" + "="*60)
    print("FINAL RESULTS - Error Recovery")
    print("="*60)
    for model, result in results.items():
        ambiguous = "✅" if result["ambiguous"] else "⚠️"
        correction = "✅" if result["correction"] else "⚠️"
        print(f"{model}: Ambiguous={ambiguous}  Correction={correction}")
