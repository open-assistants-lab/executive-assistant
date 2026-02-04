#!/bin/bash
cd /Users/eddy/Developer/Langgraph/ken

pkill -f executive_assistant 2>/dev/null
sleep 2

echo "Testing: kimi-k2.5:cloud (Retry)"
echo ""

export OLLAMA_DEFAULT_MODEL="kimi-k2.5:cloud"
export DEFAULT_LLM_PROVIDER="ollama"

uv run executive_assistant > /tmp/agent_kimi_retry.log 2>&1 &
AGENT_PID=$!
echo "Agent started: $AGENT_PID"
sleep 12

echo ""
echo "Test 1: Simple Onboarding"
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"hi","user_id":"kimi_retry_test","stream":false}'

sleep 2
echo ""
echo "Test 2: Role Extraction"
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"I am a data analyst. I need to track my daily work logs.","user_id":"kimi_retry_test","stream":false}'

sleep 2
echo ""
echo "Test 3: Tool Creation"
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"Yes please create it","user_id":"kimi_retry_test","stream":false}'
