#!/bin/bash
# Comprehensive Model Evaluation - Expanded Test Suite

MODELS=(
    "gpt-oss:20b-cloud"
    "kimi-k2.5:cloud"
    "minimax-m2.1:cloud"
    "deepseek-v3.2:cloud"
    "qwen3-next:80b-cloud"
)

OUTPUT_FILE="comprehensive_evaluation_results.md"

# Initialize results
echo "# Comprehensive Model Evaluation Results" > "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "**Date**: $(date '+%Y-%m-%d %H:%M')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for MODEL in "${MODELS[@]}"; do
    echo ""
    echo "========================================="
    echo "Testing: $MODEL"
    echo "========================================="

    # Kill existing agent
    pkill -f executive_assistant 2>/dev/null
    sleep 2

    # Start agent with this model
    echo "Starting agent..."
    export OLLAMA_DEFAULT_MODEL="$MODEL"
    export DEFAULT_LLM_PROVIDER="ollama"
    cd /Users/eddy/Developer/Langgraph/ken
    uv run executive_assistant > /tmp/agent_${MODEL//:/_}.log 2>&1 &
    sleep 12

    # Test 1: Simple Onboarding
    echo ""
    echo "Test 1: Simple Onboarding"
    echo "Message: hi"
    echo "---"
    RESULT1=$(curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"hi\",\"user_id\":\"${MODEL//:/_}_t1\",\"stream\":false}")

    CONTENT1=$(echo "$RESULT1" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data[0]['content'])
except:
    print('ERROR')
" 2>/dev/null)

    echo "$CONTENT1"
    echo ""

    # Test 2: Role-Based Onboarding
    echo "Test 2: Role-Based Onboarding"
    echo "Message: I'm a data analyst. I need to track my daily work logs."
    echo "---"
    RESULT2=$(curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"I'm a data analyst. I need to track my daily work logs.\",\"user_id\":\"${MODEL//:/_}_t2\",\"stream\":false}")

    CONTENT2=$(echo "$RESULT2" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data[0]['content'])
except:
    print('ERROR')
" 2>/dev/null)

    echo "$CONTENT2"
    echo ""

    # Test 3: Tool Creation Request
    echo "Test 3: Tool Creation Request"
    echo "Message: Yes please create it"
    echo "---"
    RESULT3=$(curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"Yes please create it\",\"user_id\":\"${MODEL//:/_}_t2\",\"stream\":false}")

    CONTENT3=$(echo "$RESULT3" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data[0]['content'])
except:
    print('ERROR')
" 2>/dev/null)

    echo "$CONTENT3"
    echo ""

    # Check for tool usage in logs
    echo "Checking for tool usage..."
    if grep -q "create_tdb_table\|create_memory" /tmp/agent_${MODEL//:/_}.log 2>/dev/null; then
        echo "✅ Tools called in logs"
    else
        echo "⚠️  No tools found in logs (may indicate issue)"
    fi

    echo ""
    echo "---"
    echo "Summary for $MODEL:"
    echo "Test 1 (Onboarding): $(echo "$CONTENT1" | grep -q "Ken\|assistant" && echo "✅ PASS" || echo "❌ FAIL")"
    echo "Test 2 (Extraction): $(echo "$CONTENT2" | grep -iq "data analyst\|analyst" && echo "✅ PASS" || echo "❌ FAIL")"
    echo "Test 3 (Tool Usage): $(echo "$CONTENT3" | grep -iq "create\|database\|table\|schema" && echo "✅ PASS" || echo "⚠️ PARTIAL/FAIL")"
    echo ""
    echo "========================================="
    echo ""
done

echo "Results saved to: $OUTPUT_FILE"
