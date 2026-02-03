#!/bin/bash
# Test a single model with the agent
# Usage: Start agent first, then run this script

MODEL=${1:-"gpt-oss:20b-cloud"}

echo "========================================="
echo "Testing Model: $MODEL"
echo "========================================="

# Verify agent is running
if ! curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✗ Agent is not running on http://localhost:8000"
    echo "Please start the agent first with:"
    echo "  export OLLAMA_DEFAULT_MODEL=$MODEL"
    echo "  export DEFAULT_LLM_PROVIDER=ollama"
    echo "  uv run executive_assistant"
    exit 1
fi

echo "✓ Agent is running"

# Run the test
echo ""
echo "Running test script..."
uv run python tests/model_evaluation/test_models.py "$MODEL"

# Show results
if [ -f model_evaluation_results.json ]; then
    echo ""
    echo "========================================="
    echo "Results:"
    echo "========================================="
    cat model_evaluation_results.json
fi
