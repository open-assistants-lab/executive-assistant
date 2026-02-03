#!/bin/bash
cd /Users/eddy/Developer/Langgraph/ken

# Kill any existing agent
pkill -f executive_assistant 2>/dev/null
sleep 2

# Set model
export OLLAMA_DEFAULT_MODEL="gpt-oss:20b-cloud"
export DEFAULT_LLM_PROVIDER="ollama"

# Start agent
echo "Starting agent with gpt-oss:20b-cloud..."
uv run executive_assistant > /tmp/agent_gpt_test.log 2>&1 &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

# Wait for initialization
echo "Waiting for agent to initialize (10s)..."
sleep 10

# Check if running
if ps -p $AGENT_PID > /dev/null 2>&1; then
    echo "✓ Agent process is running"

    # Check health endpoint
    echo ""
    echo "Checking health endpoint..."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Agent is healthy!"

        # Run test
        echo ""
        echo "Running onboarding test..."
        curl -s -X POST http://localhost:8000/message \
          -H "Content-Type: application/json" \
          -d '{"content":"hi","user_id":"gpt_test_user","stream":false}' | python3 -m json.tool

        echo ""
        echo "Stopping agent..."
        kill $AGENT_PID 2>/dev/null
        wait $AGENT_PID 2>/dev/null
        echo "✓ Test complete"
    else
        echo "✗ Agent not responding on health endpoint"
        echo "Check logs: tail -20 /tmp/agent_gpt_test.log"
    fi
else
    echo "✗ Agent process died"
    echo "Check logs: tail -50 /tmp/agent_gpt_test.log"
fi
