#!/bin/bash
cd /Users/eddy/Developer/Langgraph/ken

pkill -f executive_assistant 2>/dev/null
sleep 2

echo "Testing: claude-sonnet-4-5-20250929 (Anthropic)"
echo ""

export DEFAULT_LLM_PROVIDER="anthropic"
export ANTHROPIC_MODEL="claude-sonnet-4-5-20250929"

uv run executive_assistant > /tmp/agent_anthropic_claude.log 2>&1 &
AGENT_PID=$!
echo "Agent started: $AGENT_PID"
sleep 12

echo ""
echo "Test 1: Simple Onboarding"
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"hi","user_id":"anthropic_claude","stream":false}' | python3 -m json.tool

sleep 2
echo ""
echo "Test 2: Role Extraction"
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"I am a data analyst. I need to track my daily work logs.","user_id":"anthropic_claude","stream":false}' | python3 -m json.tool

sleep 2
echo ""
echo "Test 3: Tool Creation"
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"content":"Yes please create it","user_id":"anthropic_claude","stream":false}' | python3 -m json.tool

echo ""
echo ""
echo "Checking memories stored..."
sqlite3 data/users/http_anthropic_claude/mem/mem.db "SELECT key, content FROM memories WHERE memory_type='profile' OR memory_type='fact' LIMIT 5;" 2>/dev/null || echo "No memories found"

echo ""
echo "Full log: /tmp/agent_anthropic_claude.log"
