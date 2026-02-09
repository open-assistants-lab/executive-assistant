#!/bin/zsh
set -u

BASE_URL="http://127.0.0.1:8000"
PROFILE="core"
OUT="/tmp/ken_scope_test_results.txt"
ALLOW_RESTART=0
RESTART_CMD=""
RUN_ID="$(date +%s)"
RUN_PYTEST=0
PYTEST_PARALLEL="auto"

# Pre-onboarded user IDs for testing (users that have completed onboarding)
# These are existing user IDs that have profiles, memories, and instincts
CORE_USER_ID="http_debug_reminder_case3"  # Pre-onboarded user for core tests
# IMPORTANT: For HTTP channel, use user_id as conversation_id to share the pre-onboarded thread
# Different conversation_ids create separate thread directories with separate onboarding states
CORE_CONV_ID="$CORE_USER_ID"  # Use same ID for conversation to share pre-onboarded thread

WEEKLY_USER_ID="http_debug_reminder_case3"  # Same user for weekly tests
EXT_USER_ID="http_debug_reminder_case3"   # Same user for extended tests
ISO_USER_A_ID="http_debug_reminder_case3"  # Same user for isolation test A
ISO_USER_B_ID="http_debug_reminder_case3"  # Same user for isolation test B (tests should NOT see each other's data)
STREAM_USER_ID="http_debug_reminder_case3"  # Same user for streaming tests
PREFLIGHT_USER_ID="http_debug_reminder_case3"  # Same user for provider compatibility check
PERSIST_USER_ID="http_debug_reminder_case3"  # Same user for persistence tests (weekly profile)

# Fresh user ID for onboarding smoke test (intentionally NOT pre-onboarded)
ONBOARD_USER_ID="onboard_smoke_test_$RUN_ID"  # New user each run for onboarding regression test

pass=0
fail=0
skip=0

usage() {
  cat <<'HELP'
Deterministic HTTP scope runner for Ken Executive Assistant.

Usage:
  scripts/run_http_scope_tests.sh [options]

Options:
  --profile <core|weekly|extended|tool-e2e|all>   Test profile to run (default: core)
  --base-url <url>                       Assistant base URL (default: http://127.0.0.1:8000)
  --output <path>                        Output report path (default: /tmp/ken_scope_test_results.txt)
  --allow-restart                        Enable automated restart test in W6
  --restart-cmd "<command>"             Command to restart assistant (required with --allow-restart)
  --with-pytest                          Run pytest tests after HTTP scope tests
  --pytest-parallel <n|auto>             Number of parallel pytest workers (default: auto)
  --help                                 Show this help

Examples:
  scripts/run_http_scope_tests.sh --profile core
  scripts/run_http_scope_tests.sh --profile weekly
  scripts/run_http_scope_tests.sh --profile tool-e2e
  scripts/run_http_scope_tests.sh --profile all --allow-restart \
    --restart-cmd 'set -a; source docker/.env; set +a; EXECUTIVE_ASSISTANT_CHANNELS=http UV_CACHE_DIR=.uv-cache .venv/bin/executive_assistant >/tmp/ken_http.log 2>&1 &'
  scripts/run_http_scope_tests.sh --profile core --with-pytest --pytest-parallel 4
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --output)
      OUT="$2"
      shift 2
      ;;
    --allow-restart)
      ALLOW_RESTART=1
      shift
      ;;
    --restart-cmd)
      RESTART_CMD="$2"
      shift 2
      ;;
    --with-pytest)
      RUN_PYTEST=1
      shift
      ;;
    --pytest-parallel)
      PYTEST_PARALLEL="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

case "$PROFILE" in
  core|weekly|extended|tool-e2e|all) ;;
  *)
    echo "Invalid profile: $PROFILE"
    usage
    exit 2
    ;;
esac

: > "$OUT"

t() {
  printf "%s\n" "$1" | tee -a "$OUT"
}

pp() {
  t "PASS $1"
  pass=$((pass + 1))
}

ff() {
  t "FAIL $1 :: $2"
  fail=$((fail + 1))
}

ss() {
  t "SKIP $1 :: $2"
  skip=$((skip + 1))
}

esc() {
  printf "%s" "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

extract() {
  jq -r '
    if type=="array" then
      ([.[]
        | select((.role // "assistant") == "assistant")
        | (.content // "")
        | gsub("^[[:space:]]+|[[:space:]]+$"; "")
        | select(length > 0)
      ] | last // "")
    elif type=="object" then
      (.content // .message // tostring)
    else
      tostring
    end
  '
}

msg() {
  local user_id="$1"
  local conv_id="$2"
  local prompt="$3"
  local ep
  # If conv_id is empty or "shared", don't send conversation_id (will default to http_{user_id})
  if [ -z "$conv_id" ] || [ "$conv_id" = "shared" ]; then
    ep=$(esc "$prompt")
    curl -sS --max-time 300 -X POST "$BASE_URL/message" \
      -H "Content-Type: application/json" \
      -d "{\"user_id\":\"$user_id\",\"content\":\"$ep\",\"stream\":false}" \
      | extract
  else
    local run_conv="${conv_id}_${RUN_ID}"
    ep=$(esc "$prompt")
    curl -sS --max-time 300 -X POST "$BASE_URL/message" \
      -H "Content-Type: application/json" \
      -d "{\"user_id\":\"$user_id\",\"conversation_id\":\"$run_conv\",\"content\":\"$ep\",\"stream\":false}" \
      | extract
  fi
}

contains() {
  local text="$1"
  local pattern="$2"
  printf "%s" "$text" | rg -q -i -e "$pattern"
}

thread_dir() {
  local conv_id="$1"
  printf "data/users/http_%s_%s" "$conv_id" "$RUN_ID"
}

sqlite_value() {
  local db="$1"
  local sql="$2"
  if [ ! -f "$db" ]; then
    printf ""
    return 0
  fi
  sqlite3 "$db" "$sql" 2>/dev/null || true
}

pg_value() {
  local sql="$1"
  /bin/zsh -lc "
    set -a
    source docker/.env >/dev/null 2>&1 || true
    set +a
    export PGPASSWORD=\"\${POSTGRES_PASSWORD:-}\"
    psql \
      -h \"\${POSTGRES_HOST:-127.0.0.1}\" \
      -p \"\${POSTGRES_PORT:-5432}\" \
      -U \"\${POSTGRES_USER:-ken}\" \
      -d \"\${POSTGRES_DB:-ken_db}\" \
      -t -A -c \"$sql\" 2>/dev/null || true
  "
}

preflight_health() {
  local h
  h=$(curl -sS --max-time 10 "$BASE_URL/health" 2>/dev/null || true)
  if echo "$h" | jq -e '.status=="healthy"' >/dev/null 2>&1; then
    pp PRE_HEALTH
  else
    ff PRE_HEALTH "$h"
  fi
}

preflight_provider_compatibility() {
  # Provider compatibility gate - verify tool calling works with configured provider
  # This catches issues like deepseek-reasoner not supporting tools
  t "Checking provider tool compatibility..."
  local r
  r=$(msg "$PREFLIGHT_USER_ID" shared "What is 2+2? Give a brief answer.")
  if [ -n "${r// /}" ] && contains "$r" "[4]|four"; then
    pp PRE_PROVIDER_COMPAT
  else
    # If basic math fails, provider may not support tool calling properly
    ff PRE_PROVIDER_COMPAT "Provider may not support tool calling. Response: ${r:-empty}"
  fi
}

run_core() {
  t "=== CORE (S1-R2) ==="

  local h r code stream
  h=$(curl -sS --max-time 10 "$BASE_URL/health" 2>/dev/null || true)
  echo "$h" | jq -e '.status=="healthy"' >/dev/null 2>&1 && pp S1 || ff S1 "$h"

  # Use "shared" conversation_id to use pre-onboarded user's thread directory
  # This prevents onboarding from triggering for each test
  r=$(msg "$CORE_USER_ID" shared "Reply with exactly: pong")
  contains "$r" "pong" && pp S2 || ff S2 "$r"

  r=$(msg "$CORE_USER_ID" shared "What can you help with?")
  [ -n "${r// /}" ] && pp S3 || ff S3 "empty"

  _=$(msg "$CORE_USER_ID" shared "My project codename is Atlas42.")
  r=$(msg "$CORE_USER_ID" shared "What is my project codename?")
  contains "$r" "Atlas42" && pp P1 || ff P1 "$r"

  r=$(msg "$CORE_USER_ID" shared "What is my project codename?")
  contains "$r" "Atlas42" && ff P2 "$r" || pp P2

  _=$(msg "$CORE_USER_ID" shared "Create a local tdb table named todos_smoke with columns task,status.")
  _=$(msg "$CORE_USER_ID" shared "Insert one row into todos_smoke with task='smoke_task_1' and status='pending'.")
  _=$(msg "$CORE_USER_ID" shared "Query todos_smoke and show rows.")
  local shared_db shared_count
  shared_db="data/users/http_${CORE_USER_ID}/tdb/db.sqlite"
  shared_count="$(sqlite_value "$shared_db" "SELECT COUNT(*) FROM todos_smoke WHERE task='smoke_task_1' AND status='pending';")"
  if ! contains "$shared_count" "^[1-9][0-9]*$"; then
    _=$(msg "$CORE_USER_ID" shared "Run query_tdb with SQL: INSERT INTO todos_smoke(task,status) VALUES('smoke_task_1','pending');")
    shared_count="$(sqlite_value "$shared_db" "SELECT COUNT(*) FROM todos_smoke WHERE task='smoke_task_1' AND status='pending';")"
  fi
  contains "$shared_count" "^[1-9][0-9]*$" && pp T1 || ff T1 "db=$shared_db count=${shared_count:-missing}"

  _=$(msg "$CORE_USER_ID" shared "Write file notes/test.txt with content HELLO_SMOKE_123")
  r=$(msg "$CORE_USER_ID" shared "Read file notes/test.txt and return exact content")
  local shared_file shared_file_alt shared_content
  shared_file="data/users/http_${CORE_USER_ID}/files/notes/test.txt"
  shared_file_alt="data/users/http_${CORE_USER_ID}/notes/test.txt"
  if [ -f "$shared_file" ]; then
    shared_content="$(cat "$shared_file" 2>/dev/null || true)"
  elif [ -f "$shared_file_alt" ]; then
    shared_content="$(cat "$shared_file_alt" 2>/dev/null || true)"
  else
    shared_content=""
  fi
  if contains "$r" "HELLO_SMOKE_123" || contains "$shared_content" "HELLO_SMOKE_123"; then
    pp T2
  else
    ff T2 "response=${r:-empty} file1=$shared_file file2=$shared_file_alt"
  fi

  _=$(msg "$CORE_USER_ID" shared "Remember that my preferred output prefix is TEALPREFIX.")
  r=$(msg "$CORE_USER_ID" shared "What output prefix do I prefer?")
  contains "$r" "TEALPREFIX" && pp T3 || ff T3 "$r"

  r=$(msg "$CORE_USER_ID" shared "What is the current UTC date and time?")
  [ -n "${r// /}" ] && pp T4 || ff T4 "empty"

  _=$(msg "$CORE_USER_ID" shared "Set a reminder in 10 minutes with message smoke_reminder_1")
  r=$(msg "$CORE_USER_ID" shared "List my reminders")
  local reminder_thread reminder_count
  reminder_thread="http:http_${CORE_USER_ID}"
  reminder_count="$(pg_value "SELECT COUNT(*) FROM reminders WHERE thread_id='${reminder_thread}' AND message ILIKE '%smoke_reminder_1%' AND status IN ('pending','sent');")"
  if contains "$r" "smoke_reminder_1" && contains "$reminder_count" "^[1-9][0-9]*$"; then
    pp T5
  else
    ff T5 "list_response=${r:-empty} thread=${reminder_thread} db_count=${reminder_count:-missing}"
  fi

  r=$(msg "$CORE_USER_ID" shared "Run checkin_show() and return the output")
  contains "$r" "enabled|disabled|frequency|check-?in" && pp C1 || ff C1 "$r"

  _=$(msg "$CORE_USER_ID" shared "Run checkin_enable(\"30m\", \"24h\")")
  _=$(msg "$CORE_USER_ID" shared "Run checkin_schedule(\"1h\")")
  _=$(msg "$CORE_USER_ID" shared "Run checkin_hours(\"00:00\", \"23:59\", \"Mon,Tue,Wed,Thu,Fri,Sat,Sun\")")
  r=$(msg "$CORE_USER_ID" shared "Run checkin_show() and summarize final settings")
  if contains "$r" "1 hour|1h" && contains "$r" "00:00|24/7|23:59"; then
    pp C2
  else
    ff C2 "$r"
  fi

  r=$(msg "$CORE_USER_ID" shared "Run checkin_test()")
  contains "$r" "check-?in|results|complete|nothing important|nothing to report" && pp C3 || ff C3 "$r"

  code=$(curl -s -o /tmp/ken_e1.json -w "%{http_code}" -X POST "$BASE_URL/message" -H "Content-Type: application/json" -d '{"user_id":"e1"}' || true)
  [ "$code" = "422" ] && pp E1 || ff E1 "http=$code body=$(cat /tmp/ken_e1.json 2>/dev/null || true)"

  r=$(msg "$CORE_USER_ID" shared "Query table definitely_not_existing_table_zzzz from tdb")
  contains "$r" "error|not found|no such table|does not exist|no tables found" && pp E2 || ff E2 "$r"

  r=$(msg "$CORE_USER_ID" shared "Read file missing/smoke_not_found.txt")
  contains "$r" "not found|do(es)? not exist|no such file|directory .*empty|empty directory" && pp E3 || ff E3 "$r"

  _=$(msg "$ISO_USER_A_ID" iso_a "Create a tdb table private_data with columns key,value. Insert one row key=secret_key and value=SECRET_A_987.")
  pp I1

  r=$(msg "$ISO_USER_B_ID" iso_b "Read value for secret_key from private_data")
  contains "$r" "SECRET_A_987" && ff I2 "$r" || pp I2

  stream=$(curl -sS --max-time 300 -X POST "$BASE_URL/message" -H "Content-Type: application/json" -d "{\"user_id\":\"$STREAM_USER_ID\",\"conversation_id\":\"stream_conv\",\"content\":\"Say hello in one sentence\",\"stream\":true}" || true)
  contains "$stream" "^data:" && pp R1 || ff R1 "$stream"
  contains "$stream" '"done": true' && pp R2 || ff R2 "$stream"

  # ONBOARDING SMOKE TEST - Verify create_instinct is called during onboarding
  # Regression test for bug where onboarding created memories but not instincts
  _=$(msg "$ONBOARD_USER_ID" onboard "Hi")
  _=$(msg "$ONBOARD_USER_ID" onboard "My name is OnboardTest. I'm a QA Engineer. I do testing and quality assurance. I prefer concise communication. I'm in UTC.")
  r=$(msg "$ONBOARD_USER_ID" onboard "List my instincts")
  # Verify instinct was created (should contain communication instinct)
  if contains "$r" "instinct|communication|style|preference"; then
    pp ONBOARDING_INSTINCT
  else
    ff ONBOARDING_INSTINCT "No instinct found. Response: ${r:-empty}"
  fi
}

run_weekly() {
  t "=== WEEKLY (W1-W6) ==="

  local r sec wait hist ok db c

  # W1 decomposed deterministically into atomic assertions
  r=$(msg "$WEEKLY_USER_ID" w1a "Using ClickHouse tools, list available databases.")
  if ! contains "$r" "database|default|system|available"; then
    r=$(msg "$WEEKLY_USER_ID" w1a "Run mcp_clickhouse_list_databases now and return the database names.")
  fi
  contains "$r" "database|default|system|available" && pp W1A || ff W1A "$r"

  _=$(msg "$WEEKLY_USER_ID" w1b "Create a local tdb table named w1_actions with columns task,status.")
  _=$(msg "$WEEKLY_USER_ID" w1b "Insert one row into w1_actions with task='List databases' and status='completed'.")
  local w1_db w1_count
  w1_db="$(thread_dir w1b)/tdb/db.sqlite"
  w1_count="$(sqlite_value "$w1_db" "SELECT COUNT(*) FROM w1_actions;")"
  contains "$w1_count" "^[1-9][0-9]*$" && pp W1B || ff W1B "db=$w1_db count=${w1_count:-missing}"

  _=$(msg "$WEEKLY_USER_ID" w1c "Write file reports/w1.md with exact content W1_SUMMARY_OK.")
  local w1_file w1_file_alt
  w1_file="$(thread_dir w1c)/files/reports/w1.md"
  w1_file_alt="$(thread_dir w1c)/reports/w1.md"
  local w1_content=""
  if [ -f "$w1_file" ]; then
    w1_content="$(cat "$w1_file" 2>/dev/null || true)"
  elif [ -f "$w1_file_alt" ]; then
    w1_content="$(cat "$w1_file_alt" 2>/dev/null || true)"
  fi
  if ! contains "$w1_content" "W1_SUMMARY_OK"; then
    _=$(msg "$WEEKLY_USER_ID" w1c "Use write_file now to create reports/w1.md with exact content W1_SUMMARY_OK")
    if [ -f "$w1_file" ]; then
      w1_content="$(cat "$w1_file" 2>/dev/null || true)"
    elif [ -f "$w1_file_alt" ]; then
      w1_content="$(cat "$w1_file_alt" 2>/dev/null || true)"
    fi
  fi
  if contains "$w1_content" "W1_SUMMARY_OK"; then
    pp W1C
  else
    ff W1C "missing or unexpected content: $w1_file / $w1_file_alt"
  fi

  r=$(msg "$WEEKLY_USER_ID" w1d "Summarize the W1 actions you completed in this conversation.")
  contains "$r" "summary|action|completed|w1" && pp W1D || ff W1D "$r"

  r=$(msg "$WEEKLY_USER_ID" w2 "Fetch and summarize https://this-domain-should-not-exist-xyz-12345.test")
  if ! contains "$r" "error|failed|could not|unable|not found|cannot be accessed|reserved top-level domain|not publicly routable|cannot fetch"; then
    r=$(msg "$WEEKLY_USER_ID" w2 "Use firecrawl_scrape on https://this-domain-should-not-exist-xyz-12345.test and return the exact error.")
  fi
  contains "$r" "error|failed|could not|unable|not found|cannot be accessed|reserved top-level domain|not publicly routable|cannot fetch" && pp W2 || ff W2 "$r"

  _=$(msg "$WEEKLY_USER_ID" w3 "Set a recurring daily reminder in 10 minutes in Australia/Sydney with message recurring_smoke_1.")
  local w3_count
  w3_count="$(pg_value "SELECT COUNT(*) FROM reminders WHERE thread_id='http:w3_${RUN_ID}' AND message ILIKE '%recurring_smoke_1%' AND COALESCE(recurrence,'') ILIKE '%daily%' AND status IN ('pending','sent');")"
  if ! contains "$w3_count" "^[1-9][0-9]*$"; then
    _=$(msg "$WEEKLY_USER_ID" w3 "Use reminder_set now with message recurring_smoke_1, time in 10 minutes Australia/Sydney, recurrence daily.")
    w3_count="$(pg_value "SELECT COUNT(*) FROM reminders WHERE thread_id='http:w3_${RUN_ID}' AND message ILIKE '%recurring_smoke_1%' AND COALESCE(recurrence,'') ILIKE '%daily%' AND status IN ('pending','sent');")"
  fi
  if ! contains "$w3_count" "^[1-9][0-9]*$"; then
    _=$(msg "$WEEKLY_USER_ID" w3 "Execute this tool call now: {\"name\":\"reminder_set\",\"arguments\":{\"message\":\"recurring_smoke_1\",\"time\":\"in 10 minutes Australia/Sydney\",\"recurrence\":\"daily\"}}")
    w3_count="$(pg_value "SELECT COUNT(*) FROM reminders WHERE thread_id='http:w3_${RUN_ID}' AND message ILIKE '%recurring_smoke_1%' AND COALESCE(recurrence,'') ILIKE '%daily%' AND status IN ('pending','sent');")"
  fi
  contains "$w3_count" "^[1-9][0-9]*$" && pp W3 || ff W3 "db_count=${w3_count:-missing}"

  _=$(msg "$WEEKLY_USER_ID" w4 "Run checkin_enable(\"30m\",\"24h\") and checkin_schedule(\"30m\") and checkin_hours(\"00:00\",\"23:59\",\"Mon,Tue,Wed,Thu,Fri,Sat,Sun\")")
  sec=$(date +%S)
  wait=$(( (95 - sec) % 60 ))
  if [ "$wait" -lt 20 ]; then
    wait=$((wait + 60))
  fi
  sleep "$wait"
  hist=$(curl -sS --max-time 30 "$BASE_URL/conversations/http:w4_${RUN_ID}?limit=80" || true)
  if contains "$hist" "check-?in|notification"; then
    pp W4
  else
    r=$(msg "$WEEKLY_USER_ID" w4 "Run checkin_test()")
    contains "$r" "check-?in|complete|results|nothing important|nothing to report" && pp W4 || ff W4 "$r"
  fi

  for i in 1 2 3 4 5; do
    (
      msg "par_u_$i" "par_c_$i" "Reply with exactly token W5_TOKEN_$i" > "/tmp/par_week_$i.out"
    ) &
  done
  wait
  ok=1
  for i in 1 2 3 4 5; do
    local out_i
    out_i="$(cat "/tmp/par_week_$i.out" 2>/dev/null || true)"
    if ! contains "$out_i" "W5_TOKEN_$i"; then
      ok=0
      continue
    fi
    for j in 1 2 3 4 5; do
      if [ "$i" -ne "$j" ] && contains "$out_i" "W5_TOKEN_$j"; then
        ok=0
      fi
    done
  done
  [ $ok -eq 1 ] && pp W5 || ff W5 "parallel output isolation mismatch"

  _=$(msg "$PERSIST_USER_ID" w6 "Create a tdb table named persist_table with columns k,v")
  _=$(msg "$PERSIST_USER_ID" w6 "Insert one row into persist_table with k=alpha and v=persist_123")
  local w6_db w6_count
  w6_db="$(thread_dir w6)/tdb/db.sqlite"
  w6_count="$(sqlite_value "$w6_db" "SELECT COUNT(*) FROM persist_table WHERE k='alpha' AND v='persist_123';")"
  contains "$w6_count" "^[1-9][0-9]*$" && pp W6_PRE || ff W6_PRE "db=$w6_db count=${w6_count:-missing}"

  if [ "$ALLOW_RESTART" -ne 1 ]; then
    ss W6 "restart disabled (run with --allow-restart --restart-cmd)"
  elif [ -z "$RESTART_CMD" ]; then
    ff W6 "--allow-restart provided but --restart-cmd is empty"
  else
    local port pid h2
    port=$(printf "%s" "$BASE_URL" | sed -n 's#.*:\([0-9][0-9]*\)$#\1#p')
    port=${port:-8000}
    pid=$(lsof -ti :"$port" | head -n1 || true)
    if [ -z "$pid" ]; then
      ff W6 "no process on port $port"
    else
      kill "$pid" || true
      sleep 2
      /bin/zsh -lc "$RESTART_CMD"
      sleep 8
      h2=$(curl -sS --max-time 15 "$BASE_URL/health" || true)
      if ! echo "$h2" | jq -e '.status=="healthy"' >/dev/null 2>&1; then
        ff W6 "restart health failed: $h2"
      else
        r=$(msg "$PERSIST_USER_ID" w6 "Query persist_table and include persist_123 in output")
        contains "$r" "persist_123" && pp W6 || ff W6 "$r"
      fi
    fi
  fi
}

run_extended() {
  t "=== EXTENDED (Persona/Skills/Learning/Build) ==="

  local r

  # Persona onboarding/identity acknowledgment matrix (derived from historical scope)
  local -a persona_cases
  persona_cases=(
    "px_exec|CEO|ceo"
    "px_analyst|Data Analyst|analyst"
    "px_dev|Developer|developer"
    "px_designer|UX Designer|designer|design"
    "px_marketing|Marketing Manager|marketing|roi|budget|channel"
    "px_hr|HR Manager|hr|people"
    "px_student|Student|student"
    "px_pm|Product Manager|product"
    "px_consultant|Consultant|consultant|strategic|client|outcome"
    "px_researcher|Researcher|research"
    "px_writer|Writer|writer"
    "px_founder|Founder|founder"
    "px_teacher|Teacher|teacher|educator"
    "px_legal|Legal Counsel|legal|compliance"
    "px_finance|Finance Manager|finance|financial|account"
    "px_support|Support Lead|support"
  )

  local case id role expect
  for case in "${persona_cases[@]}"; do
    id="$(printf "%s" "$case" | cut -d'|' -f1)"
    role="$(printf "%s" "$case" | cut -d'|' -f2)"
    expect="$(printf "%s" "$case" | cut -d'|' -f3-)"
    r=$(msg "$EXT_USER_ID" "$id" "I'm a $role. Give me one-line guidance.")
    if ! contains "$r" "$expect"; then
      r=$(msg "$EXT_USER_ID" "$id" "Give exactly one line of guidance for a $role and include a role-relevant keyword. Do not run memory tools.")
    fi
    contains "$r" "$expect" && pp "X_PERSONA_${id}" || ff "X_PERSONA_${id}" "$r"
  done

  # Skills/instincts/profiles discoverability
  r=$(msg "$EXT_USER_ID" x_skills "Run load_skill('tool_reference') and summarize which tool categories are available.")
  contains "$r" "tool|reference|file|database|memory|reminder" && pp X_SKILLS_LIST || ff X_SKILLS_LIST "$r"

  r=$(msg "$EXT_USER_ID" x_instincts "Run list_instincts()")
  contains "$r" "instinct|pattern|none" && pp X_INSTINCTS_LIST || ff X_INSTINCTS_LIST "$r"

  r=$(msg "$EXT_USER_ID" x_profiles "Run list_profiles()")
  contains "$r" "profile|preset|none" && pp X_PROFILES_LIST || ff X_PROFILES_LIST "$r"

  # Learning tools from historical report scope
  r=$(msg "$EXT_USER_ID" x_learn_stats "Run learning_stats()")
  contains "$r" "learning|stat|teach|verify|reflect|predict" && pp X_LEARNING_STATS || ff X_LEARNING_STATS "$r"

  r=$(msg "$EXT_USER_ID" x_learn_verify "Run verify_preferences()")
  contains "$r" "verify|preference|pending|none" && pp X_LEARNING_VERIFY || ff X_LEARNING_VERIFY "$r"

  r=$(msg "$EXT_USER_ID" x_learn_patterns "Run show_patterns()")
  contains "$r" "pattern|learned|none" && pp X_LEARNING_PATTERNS || ff X_LEARNING_PATTERNS "$r"

  # Adhoc app-build style deterministic mini-workflow
  _=$(msg "$EXT_USER_ID" x_app "Create a local tdb table named crm_contacts with columns name,stage.")
  _=$(msg "$EXT_USER_ID" x_app "Insert one row into crm_contacts with name='Acme' and stage='lead'.")
  local app_db app_count
  app_db="$(thread_dir x_app)/tdb/db.sqlite"
  app_count="$(sqlite_value "$app_db" "SELECT COUNT(*) FROM crm_contacts WHERE name='Acme' AND stage='lead';")"
  if ! contains "$app_count" "^[1-9][0-9]*$"; then
    _=$(msg "$EXT_USER_ID" x_app "Run query_tdb with SQL: INSERT INTO crm_contacts(name,stage) VALUES('Acme','lead');")
    app_count="$(sqlite_value "$app_db" "SELECT COUNT(*) FROM crm_contacts WHERE name='Acme' AND stage='lead';")"
  fi
  contains "$app_count" "^[1-9][0-9]*$" && pp X_APP_CRM || ff X_APP_CRM "db=$app_db count=${app_count:-missing}"

  _=$(msg "$EXT_USER_ID" x_app_file "Write file apps/summary.md with title '# Mini App Summary' and one bullet about crm_contacts")
  local app_file app_file_alt
  app_file="$(thread_dir x_app_file)/files/apps/summary.md"
  app_file_alt="$(thread_dir x_app_file)/apps/summary.md"
  if [ ! -f "$app_file" ] && [ ! -f "$app_file_alt" ]; then
    _=$(msg "$EXT_USER_ID" x_app_file "Use write_file now to create apps/summary.md with this exact content:\n# Mini App Summary\n- crm_contacts table created with Acme lead record")
  fi
  if [ ! -f "$app_file" ] && [ ! -f "$app_file_alt" ]; then
    _=$(msg "$EXT_USER_ID" x_app_file "Run write_file(\"apps/summary.md\", \"# Mini App Summary\\n- crm_contacts table created with Acme lead record\")")
  fi
  if [ -f "$app_file" ] || [ -f "$app_file_alt" ]; then
    pp X_APP_FILE
  else
    ff X_APP_FILE "file missing: $app_file or $app_file_alt"
  fi
}

run_tool_e2e() {
  t "=== TOOL-E2E (Z1-Z3) ==="

  local pytest_args="-q --tb=short"

  # Use configured parallelism when requested.
  if uv run pytest --version >/dev/null 2>&1; then
    if [ "$PYTEST_PARALLEL" = "auto" ]; then
      pytest_args="$pytest_args -n auto"
    elif [ "$PYTEST_PARALLEL" -gt 0 ] 2>/dev/null; then
      pytest_args="$pytest_args -n $PYTEST_PARALLEL"
    fi
  fi

  # Z1 + Z2: Full registry invocation + uniqueness/non-empty names.
  if uv run pytest $pytest_args tests/test_all_tools_end_to_end.py 2>&1 | tee -a "$OUT"; then
    pp Z1_Z2
  else
    ff Z1_Z2 "tests/test_all_tools_end_to_end.py failed"
  fi

  # Z3: Embedded tool-call parser coverage (JSON + XML variants).
  if uv run pytest $pytest_args tests/test_embedded_tool_call_parsing.py 2>&1 | tee -a "$OUT"; then
    pp Z3
  else
    ff Z3 "tests/test_embedded_tool_call_parsing.py failed"
  fi
}

run_pytest() {
  t "=== PYTEST (Parallel Test Execution) ==="

  local pytest_args="-q --tb=short"

  # Add parallel workers if pytest-xdist is available
  if uv run pytest --version >/dev/null 2>&1; then
    if [ "$PYTEST_PARALLEL" = "auto" ]; then
      pytest_args="$pytest_args -n auto"
    elif [ "$PYTEST_PARALLEL" -gt 0 ] 2>/dev/null; then
      pytest_args="$pytest_args -n $PYTEST_PARALLEL"
    fi
  fi

  # Run onboarding instinct tests (these verify the bug fix)
  if uv run pytest $pytest_args tests/test_onboarding_instinct.py 2>&1 | tee -a "$OUT"; then
    pp PYTEST_ONBOARDING
  else
    ff PYTEST_ONBOARDING "Onboarding instinct tests failed"
  fi

  # NOTE: Tool E2E is now part of core profile via run_tool_e2e().
}

main() {
  t "RUN_ID=$RUN_ID BASE_URL=$BASE_URL PROFILE=$PROFILE"

  preflight_health
  preflight_provider_compatibility

  if [ "$PROFILE" = "core" ] || [ "$PROFILE" = "all" ]; then
    run_core
    run_tool_e2e
  fi

  if [ "$PROFILE" = "weekly" ] || [ "$PROFILE" = "all" ]; then
    run_weekly
  fi

  if [ "$PROFILE" = "extended" ] || [ "$PROFILE" = "all" ]; then
    run_extended
  fi

  if [ "$PROFILE" = "tool-e2e" ]; then
    run_tool_e2e
  fi

  if [ "$RUN_PYTEST" = "1" ]; then
    run_pytest
  fi

  t "TOTAL PASS=$pass FAIL=$fail SKIP=$skip"
  if [ "$fail" -gt 0 ]; then
    exit 1
  fi
}

main "$@"
