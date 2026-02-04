#!/bin/bash
# Model Evaluation Test Script - Test one model at a time

MODEL=${1}
USER_ID="${MODEL//:/_}_eval"

echo "========================================="
echo "Testing: $MODEL"
echo "User ID: $USER_ID"
echo "========================================="

# Scenario 1: Simple Onboarding
echo ""
echo "Scenario 1: Simple Onboarding"
echo "Message: hi"
echo "---"
RESULT=$(curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"hi\",\"user_id\":\"$USER_ID\",\"stream\":false}")

echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data[0]['content'] if data else ''
print(content)
print()
print('--- EVALUATION ---')
has_intro = 'Ken' in content or 'assistant' in content
has_questions = 'What do you do' in content or 'What would you like' in content
has_context = 'help you better' in content or 'personalize' in content or 'context' in content.lower()
print('Introduces agent:', has_intro)
print('Asks about role/goals:', has_questions)
print('Explains why asking:', has_context)
"
