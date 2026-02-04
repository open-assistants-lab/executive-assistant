#!/bin/bash
# Simple Comprehensive Model Evaluation
# Tests each model on 3 scenarios with clean state

MODELS=(
    "gpt-oss:20b-cloud"
    "kimi-k2.5:cloud"
    "minimax-m2.1:cloud"
    "deepseek-v3.2:cloud"
    "qwen3-next:80b-cloud"
)

echo "# Comprehensive Model Evaluation Results"
echo "Date: $(date '+%Y-%m-%d %H:%M')"
echo ""
echo "## Test Scenarios"
echo "1. Simple Onboarding: 'hi'"
echo "2. Role Extraction: 'I'm a data analyst. I need to track my daily work logs.'"
echo "3. Tool Creation: 'Yes please create it'"
echo ""

for MODEL in "${MODELS[@]}"; do
    echo "========================================="
    echo "MODEL: $MODEL"
    echo "========================================="

    # Kill existing agent
    pkill -f executive_assidential 2>/dev/null
    pkill -f executive_assistant 2>/dev/null
    sleep 2

    # Clean up test user data
    rm -rf data/users/http_${MODEL//:/_}_*

    # Start agent
    export OLLAMA_DEFAULT_MODEL="$MODEL"
    export DEFAULT_LLM_PROVIDER="ollama"
    cd /Users/eddy/Developer/Langgraph/ken
    uv run executive_assistant > /tmp/agent_${MODEL//:/_}.log 2>&1 &
    sleep 12

    # Test 1
    echo ""
    echo "Test 1: Simple Onboarding"
    echo "---"
    curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"hi\",\"user_id\":\"${MODEL//:/_}_s1\",\"stream\":false}" \
        | python3 -m json.tool | grep -A1 '"content"' | head -20

    sleep 2

    # Test 2
    echo ""
    echo "Test 2: Role Extraction"
    echo "---"
    curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"I'm a data analyst. I need to track my daily work logs.\",\"user_id\":\"${MODEL//:/_}_s1\",\"stream\":false}" \
        | python3 -m json.tool | grep -A1 '"content"' | head -20

    sleep 2

    # Test 3
    echo ""
    echo "Test 3: Tool Creation"
    echo "---"
    curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"Yes please create it\",\"user_id\":\"${MODEL//:/_}_s1\",\"stream\":false}" \
        | python3 -m json.tool | grep -A1 '"content"' | head -20

    echo ""
    echo ""
    echo "Checking memories stored..."
    sqlite3 data/users/http_${MODEL//:/_}_s1/mem/mem.db "SELECT key, content FROM memories WHERE memory_type='profile' OR memory_type='fact' LIMIT 5;" 2>/dev/null || echo "No memories found"

    echo ""
    echo "---"
    echo ""
done
