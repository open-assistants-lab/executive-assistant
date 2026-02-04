#!/bin/bash
# Comprehensive Model Evaluation Test
# Tests all 5 models on Scenario 1, documents results

MODELS=(
    "gpt-oss:20b-cloud"
    "kimi-k2.5:cloud"
    "minimax-m2.1:cloud"
    "deepseek-v3.2:cloud"
    "qwen3-next:80b-cloud"
)

OUTPUT_FILE="model_evaluation_results.md"

# Initialize results file
echo "# Model Evaluation Results" > "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "**Date**: $(date '+%Y-%m-%d %H:%M')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "## Scenario 1: Simple Onboarding" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "**User Message**: \`hi\`" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "| Model | Response Quality | Introduces Agent | Asks Questions | Explains Why | Notes |" >> "$OUTPUT_FILE"
echo "|-------|----------------|------------------|----------------|-------------|-------|" >> "$OUTPUT_FILE"

for MODEL in "${MODELS[@]}"; do
    echo ""
    echo "========================================="
    echo "Testing: $MODEL"
    echo "========================================="

    # Kill existing agent
    pkill -f executive_assistant 2>/dev/null
    sleep 3

    # Start agent with this model
    echo "Starting agent with $MODEL..."
    export OLLAMA_DEFAULT_MODEL="$MODEL"
    export DEFAULT_LLM_PROVIDER="ollama"
    cd /Users/eddy/Developer/Langgraph/ken
    uv run executive_assistant > /tmp/agent_${MODEL//:/_}.log 2>&1 &
    sleep 12

    # Test the model
    echo "Testing onboarding..."
    USER_ID="${MODEL//:/_}_test"

    RESULT=$(curl -s -X POST http://localhost:8000/message \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"hi\",\"user_id\":\"$USER_ID\",\"stream\":false}" 2>/dev/null)

    # Extract and evaluate
    CONTENT=$(echo "$RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data[0]['content'])
except:
    print('')
" 2>/dev/null)

    # Check criteria
    HAS_INTRO=$(echo "$CONTENT" | grep -i -c "ken\|assistant")
    HAS_QUESTIONS=$(echo "$CONTENT" | grep -c "What do you do\|What would you like")
    HAS_CONTEXT=$(echo "$CONTENT" | grep -i -c "help you better\|personalize\|context")

    # Rate response quality (manual assessment will be needed)
    if [ -n "$CONTENT" ]; then
        # Basic quality check
        WORD_COUNT=$(echo "$CONTENT" | wc -w | tr -d ' ')
        if [ $WORD_COUNT -lt 20 ]; then
            QUALITY="Too brief"
        elif [ $WORD_COUNT -gt 100 ]; then
            QUALITY="Too verbose"
        else
            QUALITY="Good"
        fi
    else
        QUALITY="ERROR"
        HAS_INTRO=0
        HAS_QUESTIONS=0
        HAS_CONTEXT=0
    fi

    # Add to results
    INTRO_STATUS=$( [ $HAS_INTRO -gt 0 ] && echo "✅" || echo "❌")
    QUESTION_STATUS=$( [ $HAS_QUESTIONS -gt 0 ] && echo "✅" || echo "❌")
    CONTEXT_STATUS=$( [ $HAS_CONTEXT -gt 0 ] && echo "✅" || echo "❌")

    echo "| $MODEL | $QUALITY | $INTRO_STATUS | $QUESTION_STATUS | $CONTEXT_STATUS | $(echo $CONTENT | head -c 50)... |" >> "$OUTPUT_FILE"

    # Display result
    echo ""
    echo "Response:"
    echo "$CONTENT"
    echo ""
    echo "---"
    echo "Quality: $QUALITY | Intro: $HAS_INTRO | Questions: $HAS_QUESTIONS | Context: $HAS_CONTEXT"
done

echo ""
echo "========================================="
echo "All tests complete!"
echo "Results saved to: $OUTPUT_FILE"
echo "========================================="