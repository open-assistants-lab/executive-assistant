#!/bin/bash
# Model Evaluation Test Script
# Usage: ./run_model_test.sh <model_name>

MODEL=${1:-"gpt-oss:20b-cloud"}

echo "========================================="
echo "Testing Model: $MODEL"
echo "========================================="

# Kill any existing agent
pkill -f "uv run executive_assistant" 2>/dev/null
sleep 2

# Set model via environment
# Note: Use OLLAMA_DEFAULT_MODEL for ollama provider-specific override
export OLLAMA_DEFAULT_MODEL="$MODEL"
export DEFAULT_LLM_PROVIDER="ollama"

# Start agent in background
echo "Starting agent with model: $MODEL"
# Use env to ensure environment variables are passed
env OLLAMA_DEFAULT_MODEL="$OLLAMA_DEFAULT_MODEL" DEFAULT_LLM_PROVIDER="$DEFAULT_LLM_PROVIDER" uv run executive_assistant > /tmp/agent_test_${MODEL//:/_}.log 2>&1 &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

# Wait for agent to start
echo "Waiting for agent to initialize..."
sleep 8

# Check if agent is running
if ps -p $AGENT_PID > /dev/null; then
    echo "✓ Agent is running"

    # Export environment variables for test script
    export OLLAMA_DEFAULT_MODEL
    export DEFAULT_LLM_PROVIDER

    # Run the test (pass model as argument)
    echo ""
    echo "Running test script for model: $MODEL"
    uv run python tests/model_evaluation/test_models.py "$MODEL"

    # Clean up
    echo ""
    echo "Stopping agent..."
    kill $AGENT_PID 2>/dev/null
    wait $AGENT_PID 2>/dev/null
    echo "✓ Test complete"
else
    echo "✗ Failed to start agent"
    echo "Check logs: /tmp/agent_test_${MODEL//:/_}.log"
fi
